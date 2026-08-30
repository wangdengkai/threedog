import os

from threedog.db import Database
from threedog.graph.store import Store
from threedog.scan.incremental import diff
from threedog.scan.walker import walk
from threedog.util import utcnow  # noqa: F401 （任务书测试原文保留导入）


def test_walk_skips_hidden_and_links(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    f = tmp_path / "sub" / "a.txt"
    f.write_text("hello")
    metas = walk(tmp_path)
    assert [m.name for m in metas] == ["a.txt"]
    assert metas[0].ext == "txt" and metas[0].size == 5


def test_diff_incremental(tmp_path):
    db = Database(tmp_path / "t.db")
    store = Store(db)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("1")

    d1 = diff(store, walk(src))
    assert [m.name for m in d1.new] == ["a.txt"] and not d1.deleted

    d2 = diff(store, walk(src))          # 第二遍无变化
    assert not d2.new and not d2.changed and not d2.deleted

    (src / "a.txt").write_text("changed content")
    d3 = diff(store, walk(src))
    assert [m.name for m in d3.changed] == ["a.txt"]

    (src / "a.txt").unlink()
    d4 = diff(store, walk(src))
    assert len(d4.deleted) == 1
    db.close()


def test_diff_scoped_to_root(tmp_path):
    # C2 回归：扫描第二个根目录时不得把第一个根的文件全部误标删除。
    db = Database(tmp_path / "t.db")
    store = Store(db)
    r1 = tmp_path / "r1"
    r2 = tmp_path / "r2"
    r1.mkdir()
    r2.mkdir()
    (r1 / "a.txt").write_text("a")
    (r2 / "b.txt").write_text("b")

    diff(store, walk(r1), root=str(r1))
    d2 = diff(store, walk(r2), root=str(r2))
    assert d2.deleted == []
    assert store.get_file(str(r1 / "a.txt"))["deleted"] == 0
    assert store.get_file(str(r2 / "b.txt"))["deleted"] == 0
    db.close()


def test_under_root_sibling_prefix_not_matched(tmp_path):
    # C2 边界：E:\a 不应匹配 E:\abc（兄弟前缀目录）。
    from threedog.scan.incremental import _under_root

    base = str(tmp_path)
    assert _under_root(base + os.sep + "a" + os.sep + "x.txt", base + os.sep + "a")
    assert not _under_root(base + os.sep + "abc" + os.sep + "x.txt", base + os.sep + "a")
    assert not _under_root(base + os.sep + "other" + os.sep + "x.txt", base + os.sep + "a")
