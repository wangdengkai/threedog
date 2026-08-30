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
