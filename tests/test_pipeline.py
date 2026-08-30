import pytest

from threedog.actions.pipeline import Pipeline
from threedog.actions.strategies import symlink_ok
from threedog.config import AppConfig
from threedog.db import Database
from threedog.graph.store import Store
from threedog.scan.incremental import diff
from threedog.scan.walker import walk
from threedog.util import utcnow

STRAT = "link" if symlink_ok() else "copy"


@pytest.fixture()
def env(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"
    (src / "a.txt").write_text("a")
    (src / "b.txt").write_text("b")
    db = Database(tmp_path / "t.db")
    store = Store(db)
    cfg = AppConfig(db_path=tmp_path / "t.db", output_dir=out, default_strategy=STRAT)
    pipe = Pipeline(store, cfg)
    diff(store, walk(src))
    sid = store.save_style({"name": "s", "structure": "gtd", "options": {},
                            "naming": {}, "presentation": {"portal": "minimal"}})
    pipe.activate_style(sid)
    yield store, pipe, src, out
    db.close()


def test_full_flow(env):
    store, pipe, src, out = env
    a, b = str(src / "a.txt"), str(src / "b.txt")
    plan = pipe.propose([(a, "收件箱"), (b, "归档")], strategy=STRAT)
    assert all(r["status"] == "ready" for r in plan["rows"])
    res = pipe.apply(plan["batch_id"])
    assert sorted(res["ok"]) == [a, b] and not res["failed"]
    assert (out / "收件箱" / "a.txt").exists()
    assert (out / "收件箱" / "INDEX.md").exists()
    assert store.active_assignment(a)["batch_id"] == plan["batch_id"]

    r = pipe.rollback(plan["batch_id"])
    assert len(r["restored"]) == 2
    assert not (out / "收件箱" / "a.txt").exists()
    assert store.active_assignment(a) is None


def test_conflict_unknown_stale(env):
    # 说明：brief 原文解包为 `store, ...` 但该测试未用到 store，ruff RUF059 报错；
    # 最小修正为 `_store`（与 brief 其余测试的未用变量命名一致）。
    _store, pipe, src, out = env
    (out / "收件箱").mkdir(parents=True)
    (out / "收件箱" / "a.txt").write_text("占位")
    plan = pipe.propose([(str(src / "a.txt"), "收件箱"),
                         (str(src / "nope.txt"), "归档")], strategy=STRAT)
    by = {r["src"]: r["status"] for r in plan["rows"]}
    assert by[str(src / "a.txt")] == "conflict"
    assert by[str(src / "nope.txt")] == "unknown_file"
    res = pipe.apply(plan["batch_id"])
    assert res["ok"] == [] and len(res["skipped"]) == 2


def test_expired_batch(env):
    store, pipe, _src, _out = env
    store.save_batch("dead", {"strategy": "copy", "rows": []}, utcnow(), ttl_hours=0)
    with pytest.raises(RuntimeError, match="过期"):
        pipe.apply("dead")


def test_reactivate_style_keeps_assignments(env):
    # C1 回归：风格有任何 assignment 后再次 activate_style，此前 DELETE categories
    # 触发 FOREIGN KEY 约束崩溃；修复后归属与导读均保留。
    store, pipe, src, _out = env
    a = str(src / "a.txt")
    plan = pipe.propose([(a, "收件箱")], strategy=STRAT)
    pipe.apply(plan["batch_id"])
    sid = store.get_active_style_id()
    store.set_narration(sid, "收件箱", "收件箱导读。")

    pipe.activate_style(sid)  # 修复前：sqlite3.IntegrityError

    assign = store.active_assignment(a)
    assert assign is not None
    assert [f["path"] for f in store.files_in_category(assign["category_id"])] == [a]
    rows = {r["path_raw"]: r["narration"] for r in store.categories_of(sid)}
    assert rows["收件箱"] == "收件箱导读。"


def test_propose_duplicate_dst_conflict(env):
    # C3 回归：同一批次两个同名文件进同一分类，后者应为 conflict 而非 ready，
    # 避免 copy/move 执行时静默覆盖（move 下首个文件唯一副本会被毁掉）。
    store, pipe, src, out = env
    d1, d2 = src / "d1", src / "d2"
    d1.mkdir()
    d2.mkdir()
    (d1 / "r.txt").write_text("one", encoding="utf-8")
    (d2 / "r.txt").write_text("two", encoding="utf-8")
    diff(store, walk(src), root=str(src))

    plan = pipe.propose([(str(d1 / "r.txt"), "收件箱"),
                         (str(d2 / "r.txt"), "收件箱")], strategy="copy")
    statuses = [r["status"] for r in plan["rows"]]
    assert statuses == ["ready", "conflict"]
    assert plan["rows"][1]["note"] == "目标已在本批次中"

    res = pipe.apply(plan["batch_id"])
    assert res["ok"] == [str(d1 / "r.txt")]
    assert res["skipped"] == [str(d2 / "r.txt")]
    # 两个源文件都完好，目标侧恰好一份（内容为首个文件）
    assert (d1 / "r.txt").read_text(encoding="utf-8") == "one"
    assert (d2 / "r.txt").read_text(encoding="utf-8") == "two"
    dsts = list((out / "收件箱").glob("r.txt"))
    assert len(dsts) == 1
    assert dsts[0].read_text(encoding="utf-8") == "one"


def test_write_portal(env):
    _store, pipe, src, out = env
    a = str(src / "a.txt")
    plan = pipe.propose([(a, "归档")], strategy=STRAT)
    pipe.apply(plan["batch_id"])
    pipe.write_portal("归档", "这是归档导读。")
    content = (out / "归档" / "INDEX.md").read_text(encoding="utf-8")
    assert "这是归档导读。" in content and "a.txt" in content
