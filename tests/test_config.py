from pathlib import Path

from threedog.config import AppConfig, config_dir, load_config, save_config


def test_config_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREEDOG_HOME", str(tmp_path))
    cfg = AppConfig(db_path=tmp_path / "db.sqlite3", output_dir=tmp_path / "out")
    p = save_config(cfg)
    assert p == tmp_path / "config.toml"
    loaded = load_config()
    assert loaded.db_path == cfg.db_path
    assert loaded.default_strategy == "link"
    assert config_dir() == tmp_path


def test_load_creates_dirs(tmp_path: Path):
    cfg = AppConfig(db_path=tmp_path / "a/db.sqlite3", output_dir=tmp_path / "b/out")
    p = save_config(cfg, explicit=tmp_path / "cfg.toml")
    loaded = load_config(explicit=p)
    assert loaded.db_path.parent.exists()
    assert loaded.output_dir.exists()
