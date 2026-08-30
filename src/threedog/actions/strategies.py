from __future__ import annotations

import os
import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path


def long_path(p: Path) -> str:
    s = str(p)
    if os.name == "nt" and not s.startswith("\\\\?\\") and len(s) > 240:
        return "\\\\?\\" + s
    return s


_symlink_ok: bool | None = None


def symlink_ok() -> bool:
    global _symlink_ok
    if _symlink_ok is None:
        try:
            with tempfile.TemporaryDirectory() as td:
                src = Path(td) / "s.txt"
                src.write_text("x", encoding="utf-8")
                dst = Path(td) / "d.txt"
                os.symlink(long_path(src), long_path(dst))
            _symlink_ok = True
        except OSError:
            _symlink_ok = False
    return _symlink_ok


class Strategy(ABC):
    name: str

    @abstractmethod
    def execute(self, src: Path, dst: Path) -> str: ...

    @abstractmethod
    def rollback(self, dst: Path, info: str) -> None: ...


class LinkStrategy(Strategy):
    name = "link"

    def execute(self, src: Path, dst: Path) -> str:
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(long_path(src), long_path(dst))
        return str(src)

    def rollback(self, dst: Path, info: str) -> None:
        if dst.is_symlink() or dst.exists():
            dst.unlink()


class MoveStrategy(Strategy):
    name = "move"

    def execute(self, src: Path, dst: Path) -> str:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(long_path(src), long_path(dst))
        return str(src)

    def rollback(self, dst: Path, info: str) -> None:
        orig = Path(info)
        orig.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(long_path(dst), long_path(orig))


class CopyStrategy(Strategy):
    name = "copy"

    def execute(self, src: Path, dst: Path) -> str:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(long_path(src), long_path(dst))
        return ""

    def rollback(self, dst: Path, info: str) -> None:
        if dst.exists():
            dst.unlink()


def get_strategy(name: str) -> Strategy:
    return {"link": LinkStrategy, "move": MoveStrategy, "copy": CopyStrategy}[name]()
