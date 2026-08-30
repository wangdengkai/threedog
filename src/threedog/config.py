from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
from pydantic import BaseModel


class AppConfig(BaseModel):
    db_path: Path
    output_dir: Path
    default_strategy: Literal["link", "move", "copy"] = "link"


def config_dir() -> Path:
    env = os.environ.get("THREEDOG_HOME")
    return Path(env).expanduser() if env else Path.home() / ".threedog"


def load_config(explicit: Path | None = None) -> AppConfig:
    path = explicit or (config_dir() / "config.toml")
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    cfg = AppConfig(**data)
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def _toml_string(value: object) -> str:
    # Windows 路径含反斜杠，TOML basic string 中必须转义，否则 tomllib 解析失败
    return json.dumps(str(value), ensure_ascii=False)


def save_config(cfg: AppConfig, explicit: Path | None = None) -> Path:
    path = explicit or (config_dir() / "config.toml")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"db_path = {_toml_string(cfg.db_path)}",
        f"output_dir = {_toml_string(cfg.output_dir)}",
        f"default_strategy = {_toml_string(cfg.default_strategy)}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
