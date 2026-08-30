from pathlib import Path

import pytest
from fastmcp import Client

from threedog import server
from threedog.config import AppConfig, save_config


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("THREEDOG_HOME", str(tmp_path / "home"))
    save_config(AppConfig(db_path=tmp_path / "home/db.sqlite3",
                          output_dir=tmp_path / "home/out",
                          default_strategy="copy"))
    server.reset()
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("a")
    async with Client(server.mcp) as c:
        yield c, str(src)
    server.reset()


async def test_end_to_end_via_tools(client):
    c, src = client
    a = str(Path(src) / "a.txt")

    scan_res = await c.call_tool("scan", {"directory": src})
    assert scan_res.data["new"] == [a]

    style = await c.call_tool("create_style", {"profile": {
        "name": "s", "structure": "gtd", "options": {"inbox": False}}})
    sid = style.data["style_id"]

    layout = await c.call_tool("suggest_layout", {"style_id": sid})
    assert any(x["path_raw"] == "归档" for x in layout.data["layout"])

    await c.call_tool("set_active_style", {"style_id": sid})
    tax = await c.call_tool("taxonomy", {})
    assert any(x["path_raw"] == "归档" for x in tax.data["categories"])

    await c.call_tool("set_file_facts",
                      {"path": a, "summary": "测试文件", "keywords": ["测试"]})
    hits = await c.call_tool("search", {"query": "测试"})
    assert any(h["path"] == a for h in hits.data)

    plan = await c.call_tool("propose", {"pairs": [{"src": a, "category": "归档"}]})
    batch_id = plan.data["batch_id"]
    assert plan.data["rows"][0]["status"] == "ready"

    applied = await c.call_tool("apply", {"batch_id": batch_id})
    assert applied.data["ok"] == [a]

    portal = await c.call_tool("write_portal",
                               {"category": "归档", "markdown": "归档导读。"})
    assert portal.data["index"].endswith("INDEX.md")

    rolled = await c.call_tool("rollback", {"batch_id": batch_id})
    assert len(rolled.data["restored"]) == 1
