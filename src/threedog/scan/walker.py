from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__",
             "$RECYCLE.BIN", "System Volume Information", ".threedog"}


@dataclass
class FileMeta:
    path: str
    name: str
    ext: str
    size: int
    mtime: float


def walk(root: Path) -> list[FileMeta]:
    metas: list[FileMeta] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            fp = Path(dirpath) / fn
            if fp.is_symlink():
                continue
            st = fp.stat()
            metas.append(FileMeta(str(fp), fn, fp.suffix.lstrip(".").lower(),
                                  st.st_size, st.st_mtime))
    return metas
