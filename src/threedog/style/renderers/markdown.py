from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jinja2 import Environment

from threedog.style.renderers import Renderer

MINIMAL = """# {{ title }}
{% if narration %}
{{ narration }}
{% endif %}
{% for f in files %}
- {{ f.name }} — `{{ f.path }}`
{% endfor %}
"""

DASHBOARD = """# {{ title }}
{% if narration %}
{{ narration }}
{% endif %}
{% if stats %}
| 指标 | 值 |
|---|---|
| 文件数 | {{ stats.total }} |
| 总大小 | {{ stats.size }} B |
{% endif %}
## 文件
{% for f in files %}
- {{ f.name }}（{{ f.size }} B）
{% endfor %}
"""

TIMELINE = """# {{ title }}
{% if narration %}
{{ narration }}
{% endif %}
{% for g in groups %}
## {{ g.month }}
{% for f in g.files %}
- {{ f.name }} — `{{ f.path }}`
{% endfor %}
{% endfor %}
"""


def _month(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=timezone.utc).astimezone().strftime("%Y-%m")


class MarkdownRenderer(Renderer):
    def __init__(self, portal: str, show_stats: bool = True):
        self.portal = portal
        self.show_stats = show_stats
        self.env = Environment(autoescape=False, keep_trailing_newline=True)

    def render_index(self, title: str, files: list[dict[str, Any]],
                     stats: dict[str, Any], narration: str | None) -> str:
        if self.portal == "timeline":
            groups: dict[str, list[dict[str, Any]]] = {}
            for f in sorted(files, key=lambda x: x.get("mtime", 0), reverse=True):
                groups.setdefault(_month(f.get("mtime", 0)), []).append(f)
            return self.env.from_string(TIMELINE).render(
                title=title, narration=narration,
                groups=[{"month": m, "files": fs} for m, fs in groups.items()])
        use_stats = stats if (self.portal == "dashboard" and self.show_stats) else None
        tmpl = DASHBOARD if self.portal == "dashboard" else MINIMAL
        return self.env.from_string(tmpl).render(
            title=title, files=files, stats=use_stats, narration=narration)
