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
