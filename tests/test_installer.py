import json

from threedog.installer import setup
from threedog.installer.detect import detect


def test_deploy_skills(tmp_path):
    out = setup.deploy_skills(target=tmp_path)
    names = {p.name for p in out}
    assert {"threedog-classify-files", "threedog-find-files",
            "threedog-setup-style", "threedog-rebuild-index"} == names
    assert (tmp_path / "threedog-classify-files" / "SKILL.md").exists()
    assert (tmp_path / "threedog-classify-files" / "VERSION").exists()


def test_deploy_skills_idempotent(tmp_path):
    setup.deploy_skills(target=tmp_path)
    setup.deploy_skills(target=tmp_path)  # 覆盖不报错
    assert (tmp_path / "threedog-find-files" / "SKILL.md").exists()


def test_generic_install(tmp_path):
    p = setup.install_generic(cwd=tmp_path)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["mcpServers"]["threedog"] == {
        "command": "uvx", "args": ["threedog", "serve"]}


def test_detect_includes_generic():
    assert "generic" in detect()


def test_install_claude_code_uses_resolved_path(monkeypatch):
    # Windows 上 claude 通常以 claude.cmd/claude.exe shim 存在，subprocess 无法
    # 解析裸命令名，必须用 which 解析出的完整路径作为 argv[0]。
    calls: list[list[str]] = []
    monkeypatch.setattr(setup.shutil, "which", lambda name: "C:/fake/claude.cmd")
    monkeypatch.setattr(setup.subprocess, "run",
                        lambda argv, **kw: calls.append(argv))

    assert setup.install_claude_code() is True
    assert calls and calls[0][0] == "C:/fake/claude.cmd"
    assert calls[0][1:4] == ["mcp", "add", "--user"]


def test_install_claude_code_not_installed(monkeypatch):
    # claude 未安装时不应触发任何子进程调用。
    def boom(argv, **kw):
        raise AssertionError("claude 未安装时不应调用 subprocess.run")

    monkeypatch.setattr(setup.shutil, "which", lambda name: None)
    monkeypatch.setattr(setup.subprocess, "run", boom)

    assert setup.install_claude_code() is False
