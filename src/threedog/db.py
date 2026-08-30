from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = (Path(__file__).parent / "graph" / "schema.sql").read_text(encoding="utf-8")
VERSION = 1


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    def migrate(self) -> None:
        (v,) = self.conn.execute("PRAGMA user_version").fetchone()
        if v < 1:
            self.conn.executescript(SCHEMA)
            self.conn.execute(f"PRAGMA user_version = {VERSION}")
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()
