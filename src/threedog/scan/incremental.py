from __future__ import annotations

from dataclasses import dataclass, field

from threedog.graph.store import Store
from threedog.scan.walker import FileMeta
from threedog.util import utcnow


@dataclass
class ScanDiff:
    new: list[FileMeta] = field(default_factory=list)
    changed: list[FileMeta] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)


def diff(store: Store, metas: list[FileMeta], now: str | None = None) -> ScanDiff:
    now = now or utcnow()
    known = store.known_files()
    result = ScanDiff()
    seen: set[str] = set()
    for m in metas:
        seen.add(m.path)
        if m.path not in known:
            result.new.append(m)
            store.upsert_file(m.path, m.name, m.ext, m.size, m.mtime, now)
        elif known[m.path] != m.mtime:
            result.changed.append(m)
            store.upsert_file(m.path, m.name, m.ext, m.size, m.mtime, now)
    result.deleted = [p for p in known if p not in seen]
    store.mark_deleted(result.deleted, now)
    return result
