import json

import pytest

from threedog.db import Database
from threedog.graph.store import Store
from threedog.util import utcnow


@pytest.fixture()
def store(tmp_path):
    db = Database(tmp_path / "t.db")
    s = Store(db)
    yield s
    db.close()


def test_style_save_and_activate(store):
    sid = store.save_style({"name": "s1", "structure": "domain",
                            "options": {"domains": ["A"]}, "naming": {},
                            "presentation": {}})
    store.set_active_style(sid)
    assert store.get_active_style_id() == sid
    assert store.list_styles()[0]["name"] == "s1"


def test_categories_tree(store):
    sid = store.save_style({"name": "s1", "structure": "domain",
                            "options": {}, "naming": {}, "presentation": {}})
    store.replace_categories(sid, ["职业发展", "职业发展/证书", "生活"])
    rows = {r["path_raw"]: r for r in store.categories_of(sid)}
    assert rows["职业发展/证书"]["parent_id"] == rows["职业发展"]["id"]
    cid = store.ensure_category(sid, "职业发展/证书")  # 幂等
    assert cid == rows["职业发展/证书"]["id"]
    chain = [r["name_raw"] for r in store.chain_of(sid, "职业发展/证书")]
    assert chain == ["职业发展", "证书"]


def test_assignment_lifecycle(store):
    now = utcnow()
    store.upsert_file("f.txt", "f.txt", "txt", 1, 1.0, now)
    sid = store.save_style({"name": "s1", "structure": "gtd",
                            "options": {}, "naming": {}, "presentation": {}})
    c1 = store.ensure_category(sid, "收件箱")
    c2 = store.ensure_category(sid, "归档")
    store.upsert_assignment("f.txt", c1, "b1", "link", now)
    assert store.active_assignment("f.txt")["category_id"] == c1
    store.upsert_assignment("f.txt", c2, "b2", "link", now)  # 旧的自动 revoke
    assert store.active_assignment("f.txt")["category_id"] == c2
    assert len(store.files_in_category(c1)) == 0
    store.revoke_batch("b2")
    assert store.active_assignment("f.txt") is None


def test_replace_categories_migrates_and_prunes_assignments(store):
    # C1 补充：path_raw 仍在的 assignments 迁移到新 id；消失路径的陈旧 assignments 删除。
    now = utcnow()
    store.upsert_file("f1.txt", "f1.txt", "txt", 1, 1.0, now)
    store.upsert_file("f2.txt", "f2.txt", "txt", 1, 1.0, now)
    sid = store.save_style({"name": "s1", "structure": "domain",
                            "options": {"domains": ["A"]}, "naming": {}, "presentation": {}})
    ca = store.ensure_category(sid, "A")
    cb = store.ensure_category(sid, "B")
    store.upsert_assignment("f1.txt", ca, "b1", "link", now)
    store.upsert_assignment("f2.txt", cb, "b2", "link", now)

    store.replace_categories(sid, ["A"])  # B 从新骨架消失

    new_a = next(r for r in store.categories_of(sid) if r["path_raw"] == "A")
    assert store.active_assignment("f1.txt")["category_id"] == new_a["id"]
    assert store.active_assignment("f2.txt") is None  # 陈旧归属被删除


def test_batch_and_journal(store):
    now = utcnow()
    store.save_batch("b1", {"rows": []}, now)
    assert json.loads(store.get_batch("b1")["plan_json"]) == {"rows": []}
    store.append_journal("b1", [{"op": "link", "dst": "x"}], now)
    store.append_journal("b1", [{"op": "link", "dst": "y"}], now)
    assert [json.loads(r["action"])["dst"] for r in store.journal_of("b1")] == ["y", "x"]
    store.set_batch_status("b1", "applied")
    assert store.get_batch("b1")["status"] == "applied"


def test_overview(store):
    now = utcnow()
    store.upsert_file("a.txt", "a.txt", "txt", 1, 1.0, now)
    store.upsert_file("b.txt", "b.txt", "txt", 1, 1.0, now)
    ov = store.overview()
    assert ov["files"] == 2 and ov["unassigned"] == 2
