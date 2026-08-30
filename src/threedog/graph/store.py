from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from threedog.db import Database

_CJK = re.compile(r"([\u4e00-\u9fff])")


def fts_text(s: str) -> str:
    """CJK 逐字间插空格，让 unicode61 分词器按字建索引。"""
    return _CJK.sub(r" \1 ", s)


def fts_query(q: str) -> str:
    return '"' + " ".join(fts_text(q).split()) + '"'


class Store:
    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    # ---------- files ----------
    def upsert_file(self, path: str, name: str, ext: str,
                    size: int, mtime: float, now: str) -> int:
        # I1：写方法统一持 db._lock（跨线程共享连接时串行化写操作）
        with self.db._lock:
            self.conn.execute(
                "INSERT INTO files(path,name,ext,size,mtime,first_seen,last_seen,deleted)"
                " VALUES(?,?,?,?,?,?,?,0)"
                " ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime,"
                " last_seen=excluded.last_seen, deleted=0",
                (path, name, ext, size, mtime, now, now))
            self.conn.commit()
            row = self.conn.execute(
                "SELECT id FROM files WHERE path=?", (path,)).fetchone()
            return row["id"]

    def _fts_refresh(self, fid: int, name: str, summary: str = "", keywords: str = "[]") -> None:
        self.conn.execute("DELETE FROM file_search WHERE rowid=?", (fid,))
        self.conn.execute(
            "INSERT INTO file_search(rowid,name,summary,keywords) VALUES(?,?,?,?)",
            (fid, fts_text(name), fts_text(summary), fts_text(keywords)))

    def known_files(self) -> dict[str, float]:
        return {r["path"]: r["mtime"]
                for r in self.conn.execute("SELECT path,mtime FROM files WHERE deleted=0")}

    def mark_deleted(self, paths: list[str], now: str) -> int:
        with self.db._lock:
            n = 0
            for p in paths:
                cur = self.conn.execute(
                    "UPDATE files SET deleted=1, last_seen=? WHERE path=? AND deleted=0",
                    (now, p))
                n += cur.rowcount
            self.conn.commit()
            return n

    def get_file(self, path: str):
        return self.conn.execute("SELECT * FROM files WHERE path=?", (path,)).fetchone()

    # ---------- facts ----------
    def set_facts(self, path: str, summary: str, keywords: list[str], now: str) -> None:
        row = self.get_file(path)
        if row is None:
            raise KeyError(f"not scanned: {path}")
        kw = json.dumps(keywords, ensure_ascii=False)
        with self.db._lock:
            self.conn.execute(
                "INSERT INTO file_facts(file_id,summary,keywords,extracted_at) VALUES(?,?,?,?)"
                " ON CONFLICT(file_id) DO UPDATE SET summary=excluded.summary,"
                " keywords=excluded.keywords, extracted_at=excluded.extracted_at",
                (row["id"], summary, kw, now))
            self._fts_refresh(row["id"], row["name"], summary, kw)
            self.conn.commit()

    def get_card(self, path: str) -> dict[str, Any]:
        row = self.get_file(path)
        if row is None:
            raise KeyError(f"not scanned: {path}")
        facts = self.conn.execute(
            "SELECT * FROM file_facts WHERE file_id=?", (row["id"],)).fetchone()
        assigns = self.conn.execute(
            "SELECT a.batch_id, a.strategy, c.path_raw FROM assignments a"
            " JOIN categories c ON c.id = a.category_id"
            " WHERE a.file_id=? AND a.status='active'", (row["id"],)).fetchall()
        return {
            "path": row["path"], "name": row["name"], "ext": row["ext"],
            "size": row["size"], "mtime": row["mtime"],
            "summary": facts["summary"] if facts else "",
            "keywords": json.loads(facts["keywords"]) if facts else [],
            "assignments": [dict(a) for a in assigns],
        }

    # ---------- search ----------
    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        try:
            rows = self.conn.execute(
                "SELECT f.path, f.name, f.ext, f.deleted FROM file_search s"
                " JOIN files f ON f.id = s.rowid"
                " WHERE file_search MATCH ? LIMIT ?",
                (fts_query(query), limit)).fetchall()
        except sqlite3.Error:
            rows = []
        like = f"%{query}%"
        rows2 = self.conn.execute(
            "SELECT path, name, ext, deleted FROM files"
            " WHERE path LIKE ? AND deleted=0 LIMIT ?", (like, limit)).fetchall()
        merged: dict[str, dict] = {}
        for r in [*rows, *rows2]:
            if not r["deleted"]:
                merged.setdefault(r["path"], dict(r))
        return list(merged.values())

    # ---------- styles ----------
    def save_style(self, profile: dict) -> int:
        with self.db._lock:
            self.conn.execute(
                "INSERT INTO style_profiles(name,structure,options,naming,presentation,active)"
                " VALUES(?,?,?,?,?,?)"
                " ON CONFLICT(name) DO UPDATE SET structure=excluded.structure,"
                " options=excluded.options, naming=excluded.naming,"
                " presentation=excluded.presentation",
                (profile["name"], profile["structure"],
                 json.dumps(profile["options"], ensure_ascii=False),
                 json.dumps(profile["naming"], ensure_ascii=False),
                 json.dumps(profile["presentation"], ensure_ascii=False),
                 profile.get("active", 0)))
            self.conn.commit()
            row = self.conn.execute(
                "SELECT id FROM style_profiles WHERE name=?", (profile["name"],)).fetchone()
            return row["id"]

    def set_active_style(self, style_id: int) -> None:
        with self.db._lock:
            self.conn.execute("UPDATE style_profiles SET active=0 WHERE active=1")
            self.conn.execute("UPDATE style_profiles SET active=1 WHERE id=?", (style_id,))
            self.conn.commit()

    def get_active_style_id(self) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM style_profiles WHERE active=1").fetchone()
        return row["id"] if row else None

    def list_styles(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT id,name,structure,active FROM style_profiles ORDER BY id")]

    # ---------- categories ----------
    def _ensure_chain(self, style_id: int, raw_path: str) -> int:
        """逐级补建路径上缺失的分类节点，返回最深节点 id（幂等，不删除已有分类）。"""
        parent = None
        parts = raw_path.split("/")
        for depth, name in enumerate(parts):
            prefix = "/".join(parts[: depth + 1])
            row = self.conn.execute(
                "SELECT id FROM categories WHERE style_id=? AND path_raw=?",
                (style_id, prefix)).fetchone()
            if row is None:
                sort = self.conn.execute(
                    "SELECT COALESCE(MAX(sort),0)+1 FROM categories"
                    " WHERE style_id=? AND parent_id IS ?",
                    (style_id, parent)).fetchone()[0]
                parent = self.conn.execute(
                    "INSERT INTO categories(style_id,parent_id,name_raw,path_raw,sort)"
                    " VALUES(?,?,?,?,?)",
                    (style_id, parent, name, prefix, sort)).lastrowid
            else:
                parent = row["id"]
        return parent

    def replace_categories(self, style_id: int, raw_paths: list[str]) -> None:
        # C1：assignments.category_id 无 ON DELETE，直接 DELETE categories 会触发 FK 约束。
        # 先快照旧分类 (id, path_raw) 并把引用置 NULL（可空列），重建链后按 path_raw
        # 重指向新 id；新骨架中已消失的路径，其陈旧 assignments 直接删除。
        with self.db._lock:
            old = [(r["id"], r["path_raw"])
                   for r in self.conn.execute(
                       "SELECT id, path_raw FROM categories WHERE style_id=?",
                       (style_id,))]
            held: list = []
            if old:
                marks = ",".join("?" * len(old))
                ids = [i for i, _ in old]
                held = self.conn.execute(
                    f"SELECT id, category_id FROM assignments WHERE category_id IN ({marks})",
                    ids).fetchall()
                self.conn.execute(
                    f"UPDATE assignments SET category_id=NULL WHERE category_id IN ({marks})",
                    ids)
            self.conn.execute("DELETE FROM categories WHERE style_id=?", (style_id,))
            for p in sorted(raw_paths):
                self._ensure_chain(style_id, p)
            new = {r["path_raw"]: r["id"]
                   for r in self.conn.execute(
                       "SELECT id, path_raw FROM categories WHERE style_id=?",
                       (style_id,))}
            old_by_id = dict(old)
            for a in held:
                new_id = new.get(old_by_id[a["category_id"]])
                if new_id is not None:
                    self.conn.execute(
                        "UPDATE assignments SET category_id=? WHERE id=?",
                        (new_id, a["id"]))
                else:
                    self.conn.execute("DELETE FROM assignments WHERE id=?", (a["id"],))
            self.conn.commit()

    def ensure_category(self, style_id: int, raw_path: str) -> int:
        with self.db._lock:
            cid = self._ensure_chain(style_id, raw_path)
            self.conn.commit()
            return cid

    def categories_of(self, style_id: int) -> list:
        return self.conn.execute(
            "SELECT * FROM categories WHERE style_id=?"
            " ORDER BY parent_id IS NULL DESC, sort", (style_id,)).fetchall()

    def chain_of(self, style_id: int, raw_path: str) -> list:
        parts = raw_path.split("/")
        rows = []
        for i in range(1, len(parts) + 1):
            r = self.conn.execute(
                "SELECT * FROM categories WHERE style_id=? AND path_raw=?",
                (style_id, "/".join(parts[:i]))).fetchone()
            if r is not None:
                rows.append(r)
        return rows

    def set_narration(self, style_id: int, raw_path: str, text: str) -> None:
        with self.db._lock:
            self.conn.execute(
                "UPDATE categories SET narration=? WHERE style_id=? AND path_raw=?",
                (text, style_id, raw_path))
            self.conn.commit()

    # ---------- assignments ----------
    def upsert_assignment(self, path: str, category_id: int, batch_id: str,
                          strategy: str, now: str) -> None:
        row = self.get_file(path)
        with self.db._lock:
            self.conn.execute(
                "UPDATE assignments SET status='revoked' WHERE file_id=? AND status='active'",
                (row["id"],))
            self.conn.execute(
                "INSERT INTO assignments(file_id,category_id,batch_id,strategy,status,created_at)"
                " VALUES(?,?,?,?, 'active', ?)",
                (row["id"], category_id, batch_id, strategy, now))
            self.conn.commit()

    def active_assignment(self, path: str):
        row = self.get_file(path)
        return self.conn.execute(
            "SELECT * FROM assignments WHERE file_id=? AND status='active'",
            (row["id"],)).fetchone()

    def revoke_batch(self, batch_id: str) -> None:
        with self.db._lock:
            self.conn.execute(
                "UPDATE assignments SET status='revoked' WHERE batch_id=? AND status='active'",
                (batch_id,))
            self.conn.commit()

    def files_in_category(self, category_id: int) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT f.path, f.name, f.size, f.mtime FROM assignments a"
            " JOIN files f ON f.id = a.file_id"
            " WHERE a.category_id=? AND a.status='active' AND f.deleted=0",
            (category_id,))]

    # ---------- batches / journal ----------
    def save_batch(self, batch_id: str, plan: dict, now: str, ttl_hours: int = 24) -> None:
        from datetime import datetime, timedelta
        expires = (datetime.fromisoformat(now)
                   + timedelta(hours=ttl_hours)).isoformat()
        with self.db._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO batches(id,created_at,expires_at,plan_json,status)"
                " VALUES(?,?,?,?, 'proposed')",
                (batch_id, now, expires, json.dumps(plan, ensure_ascii=False)))
            self.conn.commit()

    def get_batch(self, batch_id: str):
        return self.conn.execute(
            "SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()

    def set_batch_status(self, batch_id: str, status: str) -> None:
        with self.db._lock:
            self.conn.execute(
                "UPDATE batches SET status=? WHERE id=?", (status, batch_id))
            self.conn.commit()

    def append_journal(self, batch_id: str, actions: list[dict], now: str) -> None:
        # seq 按批次单调递增，跨多次调用不回零，保证 journal_of 的 seq 降序 = 最新在前
        with self.db._lock:
            seq = self.conn.execute(
                "SELECT COALESCE(MAX(seq),-1)+1 FROM journal WHERE batch_id=?",
                (batch_id,)).fetchone()[0]
            for a in actions:
                self.conn.execute(
                    "INSERT INTO journal(batch_id,seq,action,status,created_at)"
                    " VALUES(?,?,?, 'done', ?)",
                    (batch_id, seq, json.dumps(a, ensure_ascii=False), now))
                seq += 1
            self.conn.commit()

    def journal_of(self, batch_id: str) -> list:
        return self.conn.execute(
            "SELECT * FROM journal WHERE batch_id=? ORDER BY seq DESC",
            (batch_id,)).fetchall()

    # ---------- overview ----------
    def overview(self) -> dict:
        def one(sql: str) -> int:
            return self.conn.execute(sql).fetchone()[0]

        return {
            "files": one("SELECT COUNT(*) FROM files WHERE deleted=0"),
            "unassigned": one(
                "SELECT COUNT(*) FROM files f WHERE f.deleted=0 AND NOT EXISTS"
                " (SELECT 1 FROM assignments a"
                "  WHERE a.file_id=f.id AND a.status='active')"),
            "styles": self.list_styles(),
            "active_style": self.get_active_style_id(),
            "recent_batches": [dict(r) for r in self.conn.execute(
                "SELECT id,status,created_at FROM batches"
                " ORDER BY created_at DESC LIMIT 5")],
        }
