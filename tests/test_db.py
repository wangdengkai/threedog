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


def test_concurrent_writes_cross_thread(tmp_path):
    # I1 回归：FastMCP 经 anyio.to_thread 在不同工作线程调用同步工具，
    # 共享连接跨线程写此前触发 ProgrammingError；修复后应无异常且行数完整。
    from concurrent.futures import ThreadPoolExecutor

    from threedog.graph.store import Store
    from threedog.util import utcnow

    db = Database(tmp_path / "t.db")
    store = Store(db)
    now = utcnow()

    def write_files():
        for i in range(50):
            store.upsert_file(f"f{i}.txt", f"f{i}.txt", "txt", 1, 1.0, now)

    def write_batches():
        for i in range(50):
            store.save_batch(f"b{i}", {"rows": []}, now)
            store.append_journal(f"b{i}", [{"op": "copy", "dst": f"d{i}"}], now)

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(write_files), ex.submit(write_batches)]
        for f in futures:  # result() 会把线程内异常重新抛出
            f.result()

    (n_files,) = db.conn.execute("SELECT COUNT(*) FROM files").fetchone()
    (n_batches,) = db.conn.execute("SELECT COUNT(*) FROM batches").fetchone()
    (n_journal,) = db.conn.execute("SELECT COUNT(*) FROM journal").fetchone()
    assert n_files == 50 and n_batches == 50 and n_journal == 50
    db.close()
