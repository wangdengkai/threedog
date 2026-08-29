from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def claude_desktop_config() -> Path | None:
    if sys.platform == "win32":
        p = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        p = (Path.home() / "Library" / "Application Support"
             / "Claude" / "claude_desktop_config.json")
    else:
        return None
    return p if p.parent.exists() else None


def detect() -> list[str]:
    found: list[str] = []
    if shutil.which("claude"):
        found.append("claude-code")
    if claude_desktop_config() is not None:
        found.append("claude-desktop")
    found.append("generic")  # .mcp.json 始终可用
    return found
