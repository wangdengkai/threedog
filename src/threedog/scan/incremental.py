from __future__ import annotations

import os
from dataclasses import dataclass, field

from threedog.graph.store import Store
from threedog.scan.walker import FileMeta
from threedog.util import utcnow


@dataclass
class ScanDiff:
    new: list[FileMeta] = field(default_factory=list)
    changed: list[FileMeta] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)


def _under_root(path: str, root: str) -> bool:
    # C2：判断 path 是否位于 root 下（Windows 大小写不敏感，normcase 归一）。
    # 带分隔符感知：E:\\a 不匹配 E:\\abc。
    p, r = os.path.normcase(path), os.path.normcase(root)
    return p.startswith(r + os.sep) or p == r


def diff(store: Store, metas: list[FileMeta], now: str | None = None,
         root: str | None = None) -> ScanDiff:
    now = now or utcnow()
    known = store.known_files()
    if root is not None:
        # 只把被扫根目录下的已知文件纳入比对，避免扫第二个根时把其它根的文件全部误标删除
        known = {p: m for p, m in known.items() if _under_root(p, root)}
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
