from __future__ import annotations

from pathlib import Path

import typer

from threedog.config import AppConfig, config_dir, load_config, save_config

app = typer.Typer(help="threedog - 风格驱动的本地文件整理 MCP server")


@app.command()
def init(
    db_path: str | None = typer.Option(None, help="数据库路径"),
    output_dir: str | None = typer.Option(None, help="归类输出目录"),
    strategy: str = typer.Option("link", help="默认写策略 link|move|copy"),
):
    """首次配置向导。"""
    cfg_dir = config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    db = db_path or typer.prompt("数据库路径", default=str(cfg_dir / "threedog.db"))
    out = output_dir or typer.prompt("输出目录", default=str(cfg_dir / "organized"))
    cfg = AppConfig(db_path=Path(db), output_dir=Path(out), default_strategy=strategy)
    save_config(cfg)

    from threedog.actions.strategies import symlink_ok
    if strategy == "link" and not symlink_ok():
        typer.secho("警告：当前环境无软链权限（Windows 需开发者模式），建议用 copy",
                    fg=typer.colors.YELLOW)
    typer.echo(f"配置已写入 {cfg_dir / 'config.toml'}")


@app.command()
def install():
    """写入 MCP 客户端配置并部署 skills。"""
    from threedog.installer import setup as setup_mod
    result = setup_mod.run()
    typer.echo(result)


@app.command()
def serve():
    """启动 MCP server（stdio）。"""
    from threedog.server import mcp
    mcp.run()


@app.command()
def scan(directory: str):
    """CLI 直接扫描目录。"""
    from threedog.db import Database
    from threedog.graph.store import Store
    from threedog.scan.incremental import diff
    from threedog.scan.walker import walk

    cfg = load_config()
    store = Store(Database(cfg.db_path))
    root = Path(directory).expanduser()
    d = diff(store, walk(root), root=str(root))
    typer.echo(f"新增 {len(d.new)} 变更 {len(d.changed)} 删除 {len(d.deleted)}")


@app.command()
def status():
    """数据库/风格/最近批次概览。"""
    from threedog.db import Database
    from threedog.graph.store import Store

    cfg = load_config()
    store = Store(Database(cfg.db_path))
    typer.echo(store.overview())
