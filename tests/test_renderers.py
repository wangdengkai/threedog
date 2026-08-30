from threedog.style.profile import Presentation
from threedog.style.renderers import get_renderer

FILES = [
    {"name": "a.txt", "path": r"E:\x\a.txt", "size": 10, "mtime": 1750000000.0},
    {"name": "b.md", "path": r"E:\x\b.md", "size": 20, "mtime": 1750000000.0},
]


def test_minimal():
    r = get_renderer(Presentation(portal="minimal"))
    out = r.render_index("职业发展", FILES, {"total": 2, "size": 30}, "导读文字")
    assert "# 职业发展" in out and "导读文字" in out and "a.txt" in out


def test_dashboard_stats():
    r = get_renderer(Presentation(portal="dashboard"))
    out = r.render_index("职业发展", FILES, {"total": 2, "size": 30}, None)
    assert "| 文件数 | 2 |" in out and "导读" not in out


def test_timeline_groups():
    r = get_renderer(Presentation(portal="timeline"))
    out = r.render_index("时间线", FILES, {}, None)
    assert "## " in out and "a.txt" in out
