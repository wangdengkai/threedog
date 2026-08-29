from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from threedog.actions.strategies import get_strategy, symlink_ok
from threedog.config import AppConfig
from threedog.graph.store import Store
from threedog.style.naming import display_name
from threedog.style.profile import StyleProfile
from threedog.style.renderers import get_renderer
from threedog.style.skeleton import build_skeleton, flatten
from threedog.util import utcnow


class Pipeline:
    def __init__(self, store: Store, config: AppConfig):
        self.store = store
        self.config = config

    # ---------- style ----------
    def profile_by_id(self, style_id: int) -> StyleProfile:
        row = self.store.conn.execute(
            "SELECT * FROM style_profiles WHERE id=?", (style_id,)).fetchone()
        return StyleProfile(id=row["id"], name=row["name"], structure=row["structure"],
                            options=json.loads(row["options"]),
                            naming=json.loads(row["naming"]),
                            presentation=json.loads(row["presentation"]))

    def active_profile(self) -> StyleProfile:
        sid = self.store.get_active_style_id()
        if sid is None:
            raise RuntimeError("没有激活的风格档案，请先 create_style + set_active_style")
        return self.profile_by_id(sid)

    def activate_style(self, style_id: int) -> dict:
        kept = {r["path_raw"]: r["narration"]
                for r in self.store.categories_of(style_id) if r["narration"]}
        profile = self.profile_by_id(style_id)
        self.store.set_active_style(style_id)
        self.store.replace_categories(style_id, flatten(build_skeleton(profile)))
        for path_raw, text in kept.items():
            self.store.set_narration(style_id, path_raw, text)
        return {"active_style": style_id}

    # ---------- display ----------
    def _display_chain(self, profile: StyleProfile, raw_path: str) -> list[str]:
        parts = [p for p in raw_path.split("/") if p]
        chain: list[str] = []
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            row = self.store.conn.execute(
                "SELECT name_raw, sort FROM categories WHERE style_id=? AND path_raw=?",
                (profile.id, prefix)).fetchone()
            raw = row["name_raw"] if row else parts[i - 1]
            idx = row["sort"] if row else 0
            chain.append(display_name(raw, profile.naming, idx))
        return chain

    def _cat_dir(self, profile: StyleProfile, raw_path: str) -> Path:
        return self.config.output_dir.joinpath(*self._display_chain(profile, raw_path))

    # ---------- portal ----------
    def _render_portal(self, profile: StyleProfile, raw_path: str) -> None:
        row = self.store.conn.execute(
            "SELECT id, narration FROM categories WHERE style_id=? AND path_raw=?",
            (profile.id, raw_path)).fetchone()
        files = self.store.files_in_category(row["id"])
        stats = {"total": len(files), "size": sum(f["size"] for f in files)}
        content = get_renderer(profile.presentation).render_index(
            title="/".join(self._display_chain(profile, raw_path)),
            files=files, stats=stats,
            narration=row["narration"] if profile.presentation.narration else None)
        cat_dir = self._cat_dir(profile, raw_path)
        cat_dir.mkdir(parents=True, exist_ok=True)
        (cat_dir / "INDEX.md").write_text(content, encoding="utf-8")

    def write_portal(self, raw_cat: str, markdown: str) -> str:
        profile = self.active_profile()
        self.store.ensure_category(profile.id, raw_cat)
        self.store.set_narration(profile.id, raw_cat, markdown)
        self._render_portal(profile, raw_cat)
        return str(self._cat_dir(profile, raw_cat) / "INDEX.md")

    # ---------- pipeline ----------
    def propose(self, pairs: list[tuple[str, str]], strategy: str | None = None) -> dict:
        strat_name = strategy or self.config.default_strategy
        profile = self.active_profile()
        batch_id = uuid.uuid4().hex[:12]
        rows: list[dict[str, Any]] = []
        for src, raw_cat in pairs:
            meta = self.store.get_file(src)
            if meta is None:
                rows.append({"src": src, "category": raw_cat, "status": "unknown_file"})
                continue
            dst = self._cat_dir(profile, raw_cat) / meta["name"]
            if dst.is_symlink() and str(dst.resolve()) == str(Path(src).resolve()):
                status = "already"
            elif dst.exists():
                status = "conflict"
            else:
                status = "ready"
            rows.append({"src": src, "category": raw_cat,
                         "dst": str(dst), "status": status})
        plan = {"batch_id": batch_id, "strategy": strat_name, "rows": rows}
        self.store.save_batch(batch_id, plan, utcnow())
        return plan

    def apply(self, batch_id: str) -> dict:
        b = self.store.get_batch(batch_id)
        if b is None:
            raise KeyError(f"batch 不存在: {batch_id}")
        if b["status"] != "proposed":
            raise RuntimeError(f"batch 状态为 {b['status']}，不能 apply")
        expires = datetime.fromisoformat(b["expires_at"])
        if expires <= datetime.now(expires.tzinfo):
            self.store.set_batch_status(batch_id, "expired")
            raise RuntimeError("preview 已过期（24h），请重新 propose")
        plan = json.loads(b["plan_json"])
        strat_name = plan["strategy"]
        if strat_name == "link" and not symlink_ok():
            raise RuntimeError("当前环境无软链权限（Windows 需开发者模式），"
                               "请用 copy/move 策略重新 propose")
        strat = get_strategy(strat_name)
        profile = self.active_profile()
        ok: list[str] = []
        failed: list[dict] = []
        skipped: list[str] = []
        journal: list[dict] = []
        affected: set[str] = set()
        for row in plan["rows"]:
            if row["status"] != "ready":
                skipped.append(row["src"])
                continue
            src = Path(row["src"])
            meta = self.store.get_file(row["src"])
            if not src.exists() or src.stat().st_mtime != meta["mtime"]:
                skipped.append(row["src"])  # stale：preview 后源文件变动
                continue
            try:
                info = strat.execute(src, Path(row["dst"]))
                cid = self.store.ensure_category(profile.id, row["category"])
                journal.append({"op": strat_name, "src": str(src), "dst": row["dst"],
                                "rollback_info": info, "category": row["category"]})
                self.store.upsert_assignment(row["src"], cid, batch_id,
                                             strat_name, utcnow())
                affected.add(row["category"])
                ok.append(row["src"])
            except OSError as e:
                failed.append({"src": row["src"], "error": str(e)})
        if journal:
            self.store.append_journal(batch_id, journal, utcnow())
        for raw_cat in affected:
            self._render_portal(profile, raw_cat)
        self.store.set_batch_status(batch_id, "partial" if failed else "applied")
        return {"ok": ok, "failed": failed, "skipped": skipped}

    def rollback(self, batch_id: str) -> dict:
        entries = self.store.journal_of(batch_id)  # seq 降序 = 执行逆序
        if not entries:
            raise KeyError(f"batch 无账本记录: {batch_id}")
        restored: list[str] = []
        failed: list[dict] = []
        cats: set[str] = set()
        for e in entries:
            a = json.loads(e["action"])
            try:
                get_strategy(a["op"]).rollback(Path(a["dst"]), a["rollback_info"])
                restored.append(a["dst"])
            except OSError as ex:
                failed.append({"dst": a["dst"], "error": str(ex)})
            cats.add(a["category"])
        self.store.revoke_batch(batch_id)
        profile = self.active_profile()
        for raw_cat in cats:
            idx = self._cat_dir(profile, raw_cat) / "INDEX.md"
            if idx.exists():
                idx.unlink()
        dirs = sorted({self._cat_dir(profile, c) for c in cats},
                      key=lambda p: len(p.parts), reverse=True)
        for d in dirs:
            for sub in sorted(d.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if sub.is_dir():
                    try:
                        sub.rmdir()
                    except OSError:
                        pass
            try:
                d.rmdir()
            except OSError:
                pass
        self.store.set_batch_status(batch_id, "rolled_back")
        return {"restored": restored, "failed": failed}
