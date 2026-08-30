from threedog.db import Database


def test_migrate_creates_tables(tmp_path):
    db = Database(tmp_path / "t.db")
    names = {
        r["name"]
        for r in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "files", "file_facts", "categories", "assignments",
        "style_profiles", "batches", "journal", "file_search",
    } <= names
    db.close()


def test_migrate_idempotent(tmp_path):
    db = Database(tmp_path / "t.db")
    (v,) = db.conn.execute("PRAGMA user_version").fetchone()
    assert v == 1
    db.close()
    db2 = Database(tmp_path / "t.db")  # 重复打开不报错、版本不变
    (v2,) = db2.conn.execute("PRAGMA user_version").fetchone()
    assert v2 == 1
    db2.close()


def test_util_utcnow():
    from threedog.util import utcnow
    assert utcnow().endswith("+00:00") or "T" in utcnow()
