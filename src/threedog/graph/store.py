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
        self.conn.execute(
            "INSERT INTO files(path,name,ext,size,mtime,first_seen,last_seen,deleted)"
            " VALUES(?,?,?,?,?,?,?,0)"
            " ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime,"
            " last_seen=excluded.last_seen, deleted=0",
            (path, name, ext, size, mtime, now, now))
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM files WHERE path=?", (path,)).fetchone()
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
