from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from threedog import __version__
from threedog.installer.detect import claude_desktop_config

SERVER = {"command": "uvx", "args": ["threedog", "serve"]}


def _skills_source() -> Path:
    return Path(__file__).parent.parent / "skills"


def deploy_skills(target: Path | None = None) -> list[Path]:
    base = target or Path.home() / ".claude" / "skills"
    base.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for src in sorted(_skills_source().iterdir()):
        if not src.is_dir() or src.name.startswith("_"):
            continue
        dst = base / f"threedog-{src.name}"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        (dst / "VERSION").write_text(__version__, encoding="utf-8")
        out.append(dst)
    return out


def install_claude_code() -> bool:
    if not shutil.which("claude"):
        return False
    subprocess.run(
        ["claude", "mcp", "add", "--user", "threedog", "--",
         "uvx", "threedog", "serve"],
        check=False)
    return True


def install_claude_desktop() -> bool:
    cfg = claude_desktop_config()
    if cfg is None:
        return False
    data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
    data.setdefault("mcpServers", {})["threedog"] = SERVER
    cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def install_generic(cwd: Path | None = None) -> Path:
    p = (cwd or Path.cwd()) / ".mcp.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    data.setdefault("mcpServers", {})["threedog"] = SERVER
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def run(clients: list[str] | None = None) -> dict:
    from threedog.installer.detect import detect
    chosen = clients or detect()
    result: dict = {}
    if "claude-code" in chosen:
        result["claude-code"] = install_claude_code()
    if "claude-desktop" in chosen:
        result["claude-desktop"] = install_claude_desktop()
    if "generic" in chosen:
        result["generic"] = str(install_generic())
    result["skills"] = [str(p) for p in deploy_skills()]
    return result
