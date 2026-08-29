import pytest

from threedog.db import Database
from threedog.graph.store import Store
from threedog.util import utcnow


@pytest.fixture()
def store(tmp_path):
    db = Database(tmp_path / "t.db")
    yield Store(db)
    db.close()


def test_upsert_and_known(store):
    now = utcnow()
    fid = store.upsert_file("a/b.txt", "b.txt", "txt", 10, 1.0, now)
    assert store.known_files() == {"a/b.txt": 1.0}
    fid2 = store.upsert_file("a/b.txt", "b.txt", "txt", 20, 2.0, now)
    assert fid2 == fid
    assert store.known_files()["a/b.txt"] == 2.0


def test_facts_card_and_chinese_search(store):
    now = utcnow()
    store.upsert_file("x/报告.md", "报告.md", "md", 5, 1.0, now)
    store.set_facts("x/报告.md", "年度总结", ["总结", "年度"], now)
    card = store.get_card("x/报告.md")
    assert card["summary"] == "年度总结"
    assert card["keywords"] == ["总结", "年度"]
    # 2 个汉字的子串查询必须命中（CJK 逐字切分）
    assert any(h["path"] == "x/报告.md" for h in store.search("总结"))
    # LIKE 兜底：按路径查
    assert any(h["path"] == "x/报告.md" for h in store.search("报告"))


def test_mark_deleted(store):
    now = utcnow()
    store.upsert_file("y/1.log", "1.log", "log", 1, 1.0, now)
    assert store.mark_deleted(["y/1.log"], now) == 1
    assert store.known_files() == {}
