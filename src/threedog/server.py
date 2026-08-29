from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from threedog.actions.pipeline import Pipeline
from threedog.config import AppConfig, load_config
from threedog.db import Database
from threedog.graph.store import Store
from threedog.scan.incremental import diff
from threedog.scan.walker import walk
from threedog.style.naming import display_name
from threedog.style.profile import StyleProfile
from threedog.style.skeleton import build_skeleton, flatten
from threedog.util import utcnow

mcp = FastMCP(
    "threedog",
    instructions="threedog：风格驱动的本地文件整理。"
                 "写操作一律先 propose 预览、经用户确认后 apply。")

_ctx: dict[str, Any] = {}


def reset() -> None:
    """测试用：清空单例，下次调用重新加载配置。"""
    _ctx.clear()


def services() -> tuple[Store, Pipeline, AppConfig]:
    if "store" not in _ctx:
        cfg = load_config()
        store = Store(Database(cfg.db_path))
        _ctx.update(store=store, pipe=Pipeline(store, cfg), cfg=cfg)
    return _ctx["store"], _ctx["pipe"], _ctx["cfg"]


# ---------- 读工具 ----------
@mcp.tool
def scan(directory: str) -> dict:
    """扫描目录，登记文件并返回 {new, changed, deleted} 路径清单。"""
    store, _pipe, _cfg = services()
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise ValueError(f"目录不存在: {directory}")
    d = diff(store, walk(root))
    return {"new": [m.path for m in d.new],
            "changed": [m.path for m in d.changed],
            "deleted": d.deleted}


@mcp.tool
def get_file_cards(paths: list[str]) -> list[dict]:
    """批量获取文件卡片：元数据+摘要+已有归类（分类判断依据）。"""
    store, _pipe, _cfg = services()
    return [store.get_card(p) for p in paths]


@mcp.tool
def search(query: str, limit: int = 20) -> list[dict]:
    """按关键词/文件名/路径检索文件。"""
    store, _pipe, _cfg = services()
    return store.search(query, limit)


@mcp.tool
def graph_overview() -> dict:
    """统计：文件数、未归类数、风格清单、最近批次。"""
    store, _pipe, _cfg = services()
    return store.overview()


@mcp.tool
def taxonomy() -> dict:
    """当前激活风格的分类树骨架。"""
    store, pipe, _cfg = services()
    profile = pipe.active_profile()
    rows = store.categories_of(profile.id)
    return {"style": profile.name, "structure": profile.structure,
            "categories": [{"path_raw": r["path_raw"], "sort": r["sort"]}
                           for r in rows]}


@mcp.tool
def suggest_layout(style_id: int) -> dict:
    """dry-run：按该风格渲染目录树显示名（不落盘）。"""
    _store, pipe, _cfg = services()
    profile = pipe.profile_by_id(style_id)
    layout = []
    for p in flatten(build_skeleton(profile)):
        display = "/".join(display_name(part, profile.naming, i)
                           for i, part in enumerate(p.split("/")))
        layout.append({"path_raw": p, "display": display})
    return {"style": profile.name, "layout": layout}


# ---------- 写工具 ----------
@mcp.tool
def create_style(profile: dict) -> dict:
    """创建/更新风格档案，返回 style_id。"""
    store, _pipe, _cfg = services()
    p = StyleProfile(**profile)
    return {"style_id": store.save_style(p.model_dump(exclude={"id"}))}


@mcp.tool
def set_active_style(style_id: int) -> dict:
    """激活风格并重建目录骨架（保留已有导读）。"""
    _store, pipe, _cfg = services()
    return pipe.activate_style(style_id)


@mcp.tool
def set_file_facts(path: str, summary: str, keywords: list[str]) -> dict:
    """写回文件摘要与关键词（供检索与后续分类参考）。"""
    store, _pipe, _cfg = services()
    store.set_facts(path, summary, keywords, utcnow())
    return {"ok": True}


@mcp.tool
def propose(pairs: list[dict], strategy: str | None = None) -> dict:
    """提交分类提案 [{src, category}]，返回预览计划（不动文件）。"""
    _store, pipe, _cfg = services()
    return pipe.propose([(p["src"], p["category"]) for p in pairs], strategy)


@mcp.tool
def apply(batch_id: str) -> dict:
    """执行预览批次（需用户已确认）。返回 ok/failed/skipped。"""
    _store, pipe, _cfg = services()
    return pipe.apply(batch_id)


@mcp.tool
def write_portal(category: str, markdown: str) -> dict:
    """写分类导读并重渲染该分类 INDEX.md。"""
    _store, pipe, _cfg = services()
    return {"index": pipe.write_portal(category, markdown)}


@mcp.tool
def rollback(batch_id: str) -> dict:
    """按账本逆序回滚一个已执行批次。"""
    _store, pipe, _cfg = services()
    return pipe.rollback(batch_id)


# ---------- prompts ----------
@mcp.prompt
def classify_files(directory: str) -> str:
    return (f"请整理 {directory}：先 scan，再 get_file_cards 批量取卡片，"
            "对照 taxonomy 按当前风格判断每个文件的分类路径（'顶层/子类'，顶层必须来自骨架，"
            "子类可新建）。有把握的打包 propose 并向用户展示预览表，用户确认后 apply；"
            "存疑的逐个询问。完成后为每个分类写 3~5 句导读并 write_portal，"
            "并用 set_file_facts 回写关键文件摘要。")


@mcp.prompt
def find_files(description: str) -> str:
    return (f"用户想找文件：{description}。用多组关键词调用 search，"
            "结合 graph_overview 与 get_file_cards 判断最可能的文件，"
            "回复路径、所在分类与相关文件。")


@mcp.prompt
def style_interview() -> str:
    return ("逐维访谈用户风格：1) 结构 domain/project/time/gtd（领域或项目清单）；"
            "2) 命名 zh/bilingual/emoji/numbered（emoji 或英文映射表）；"
            "3) 呈现 minimal/dashboard/timeline。收集完 create_style，"
            "用 suggest_layout 给用户预览目录树，满意后 set_active_style。")
