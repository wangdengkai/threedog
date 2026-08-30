from typer.testing import CliRunner

from threedog.cli import app

runner = CliRunner()


def test_init_scan_status(tmp_path, monkeypatch):
    monkeypatch.setenv("THREEDOG_HOME", str(tmp_path / "home"))
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("a")

    r = runner.invoke(app, ["init", "--db-path", str(tmp_path / "home/db.sqlite3"),
                            "--output-dir", str(tmp_path / "home/out"),
                            "--strategy", "copy"])
    assert r.exit_code == 0

    r2 = runner.invoke(app, ["scan", str(src)])
    assert r2.exit_code == 0 and "新增 1" in r2.output

    r3 = runner.invoke(app, ["status"])
    assert r3.exit_code == 0 and "'files': 1" in r3.output


def test_status_without_init(tmp_path, monkeypatch):
    monkeypatch.setenv("THREEDOG_HOME", str(tmp_path / "home"))
    r = runner.invoke(app, ["status"])
    assert r.exit_code == 1
    assert "未找到配置，请先运行: threedog init" in r.output
    assert "Traceback" not in r.output


def test_scan_without_init(tmp_path, monkeypatch):
    monkeypatch.setenv("THREEDOG_HOME", str(tmp_path / "home"))
    r = runner.invoke(app, ["scan", str(tmp_path)])
    assert r.exit_code == 1
    assert "未找到配置，请先运行: threedog init" in r.output
    assert "Traceback" not in r.output


def test_status_with_corrupt_config(tmp_path, monkeypatch):
    monkeypatch.setenv("THREEDOG_HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text('db_path = "未闭合的字符串', encoding="utf-8")
    r = runner.invoke(app, ["status"])
    assert r.exit_code == 1
    assert "配置文件损坏" in r.output
    assert "请修复或删除后重新 threedog init" in r.output
    assert "Traceback" not in r.output


def test_init_invalid_strategy(tmp_path, monkeypatch):
    monkeypatch.setenv("THREEDOG_HOME", str(tmp_path / "home"))
    r = runner.invoke(app, ["init", "--strategy", "bogus"])
    assert r.exit_code != 0
    assert "无效的写策略: bogus" in r.output
    assert "Traceback" not in r.output
    assert not (tmp_path / "home" / "config.toml").exists()
