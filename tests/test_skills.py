from pathlib import Path

SKILLS = Path(__file__).parent.parent / "src" / "threedog" / "skills"


def test_four_skills_exist_with_frontmatter():
    names = {"classify-files", "find-files", "setup-style", "rebuild-index"}
    for name in names:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---")
        assert f"name: {name}" in text
        assert "description:" in text
