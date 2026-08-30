from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from threedog.style.profile import StyleProfile


@dataclass
class CategoryNode:
    name_raw: str
    children: list[CategoryNode] = field(default_factory=list)


def build_skeleton(profile: StyleProfile) -> list[CategoryNode]:
    o = profile.options
    if profile.structure == "gtd":
        names = ["收件箱", "下一步", "资料", "归档"]
    elif profile.structure == "time":
        t = datetime.now(tz=timezone.utc).astimezone().date()
        if o.granularity == "year":
            names = [str(t.year)]
        elif o.granularity == "quarter":
            names = [f"{t.year}Q{(t.month - 1) // 3 + 1}"]
        else:
            names = [f"{t.year}-{t.month:02d}"]
    elif profile.structure == "domain":
        names = o.domains
    else:
        names = o.projects
    nodes = [CategoryNode(n) for n in names]
    if o.inbox:
        nodes.insert(0, CategoryNode("待整理"))
    return nodes


def flatten(nodes: list[CategoryNode]) -> list[str]:
    out: list[str] = []

    def rec(n: CategoryNode, prefix: str) -> None:
        path = f"{prefix}/{n.name_raw}" if prefix else n.name_raw
        out.append(path)
        for c in n.children:
            rec(c, path)

    for n in nodes:
        rec(n, "")
    return out
