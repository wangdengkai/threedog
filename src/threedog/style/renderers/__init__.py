from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from threedog.style.profile import Presentation


class Renderer(ABC):
    """门户渲染器抽象。v2 的 HTML 渲染器实现同一接口。"""

    @abstractmethod
    def render_index(self, title: str, files: list[dict[str, Any]],
                     stats: dict[str, Any], narration: str | None) -> str: ...


def get_renderer(p: Presentation) -> Renderer:
    from threedog.style.renderers.markdown import MarkdownRenderer
    return MarkdownRenderer(p.portal, show_stats=p.show_stats)
