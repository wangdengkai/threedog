# threedog MCP 重设计实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 threedog 从自建 agent 循环重构为「FastMCP server（能力与写操作）+ skills（编排）+ SQLite local-first + 风格档案」的开源可分发工具。

**Architecture:** 参照 code-review-graph 的分工——server 零 LLM 调用，读写分离，写操作全部走 preview→apply→rollback 流水线；风格引擎分两层（结构层确定性模板渲染，叙述层由 host LLM 经工具落盘）。

**Tech Stack:** Python ≥3.10、uv、FastMCP ≥3.2.4,<4、pydantic v2、jinja2、typer、SQLite+FTS5、pytest、ruff。

**Spec:** `docs/superpowers/specs/2026-08-29-threedog-mcp-redesign-design.md`

## Global Constraints

- **每个任务最后一步必须 commit 并 `git push origin main`（用户明确要求多提交多推送）**
- 依赖白名单：`fastmcp>=3.2.4,<4`、`pydantic>=2.7`、`jinja2>=3.1`、`typer>=0.12`；**禁止** openai/pyautogen/py2neo/neo4j
- server 内零 LLM 调用；所有写操作经 preview→apply 流水线
- 测试命令统一 `uv run pytest`；lint 统一 `uv run ruff check .`（line-length=100）
- Windows 兼容：路径清洗（非法字符/保留名/NFC）、`\\?\` 长路径前缀、软链测试无权限时 skipif
- 包名 `threedog`，src 布局，模块划分遵循 spec §3
- 中文提交信息，格式 `feat|fix|chore|docs|test: <摘要>`

## Spec 细化说明（计划期锁定的 4 处补充，不改变 spec 语义）

1. 新增 `batches` 表存放 preview 计划（spec §9 要求 preview 存库 24h 过期，原 schema 缺表）
2. `categories` 增加 `narration` 列（spec §8 要求叙述内容存库）
3. 删除 structure options 的 `depth`：domain/project 骨架只预生成顶层+可选收件箱，更深层路径在 apply 时按需创建；`time` 层级由 `granularity` 决定（year/quarter/month）
4. skills 放在包内 `src/threedog/skills/`（而非仓库根），随 wheel 自动分发

## 文件结构总览

```
pyproject.toml                          # 任务1 重写；任务14 加 scripts 入口
src/threedog/
  __init__.py                           # 任务1
  util.py                               # 任务3  utcnow()
  config.py                             # 任务2  AppConfig/load/save, THREEDOG_HOME
  db.py                                 # 任务3  Database + 迁移
  graph/schema.sql                      # 任务3  全部表 + FTS5
  graph/store.py                        # 任务4/5  Store（文件/检索 + 分类/风格/流水线账本）
  scan/walker.py                        # 任务6  FileMeta + walk
  scan/incremental.py                   # 任务6  ScanDiff + diff
  style/profile.py                      # 任务7  StyleProfile 族
  style/naming.py                       # 任务8  display_name/sanitize
  style/skeleton.py                     # 任务9  CategoryNode/build_skeleton/flatten
  style/renderers/__init__.py           # 任务10 Renderer 抽象 + get_renderer
  style/renderers/markdown.py           # 任务10 三套 md 模板
  actions/strategies.py                 # 任务11 link/move/copy + 长路径 + 软链探测
  actions/pipeline.py                   # 任务12 propose/apply/rollback
  server.py                             # 任务13 13 工具 + 3 prompts
  cli.py + __main__.py                  # 任务14 init/install/serve/scan/status
  installer/detect.py                   # 任务16 客户端检测
  installer/setup.py                    # 任务16 写配置 + 部署 skills
  skills/*/SKILL.md                     # 任务15 4 个 skill 源
.github/workflows/ci.yml                # 任务17
.github/workflows/publish.yml           # 任务17
README.md + README.zh-CN.md             # 任务17
docs/legacy/                            # 任务17 doc/plantuml 迁入
删除: miaomiao/ main.py example/        # 任务17
```

---

### Task 1: 项目脚手架与依赖

**Files:**
- Modify: `pyproject.toml`（整文件重写）
- Create: `src/threedog/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: 包 `threedog` 可导入；`threedog.__version__ == "0.2.0"`；dev 依赖 pytest/ruff/pytest-asyncio 就绪

- [ ] **Step 1: 重写 pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "threedog"
version = "0.2.0"
description = "风格驱动的本地文件整理 MCP server（style-driven local file organizer MCP server）"
readme = "README.md"
requires-python = ">=3.10"
license = "Apache-2.0"
authors = [{ name = "wangdengkai", email = "mrwangdengkai@163.com" }]
dependencies = [
    "fastmcp>=3.2.4,<4",
    "pydantic>=2.7",
    "jinja2>=3.1",
    "typer>=0.12",
]

[dependency-groups]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "ruff>=0.6"]

[[tool.uv.index]]
url = "https://pypi.tuna.tsinghua.edu.cn/simple"
default = true

[tool.hatch.build.targets.wheel]
packages = ["src/threedog"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]
extend-exclude = ["miaomiao", "example", "tmp", "doc"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: 写包骨架与冒烟测试**

`src/threedog/__init__.py`:

```python
__version__ = "0.2.0"
```

`tests/test_smoke.py`:

```python
import threedog


def test_version():
    assert threedog.__version__ == "0.2.0"
```

- [ ] **Step 3: 同步环境并验证**

Run: `uv sync`
Expected: 成功创建环境并安装 fastmcp/pydantic/jinja2/typer

Run: `uv run pytest -q`
Expected: `1 passed`

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 4: 提交并推送**

```bash
git add pyproject.toml uv.lock src tests
git commit -m "feat: 项目脚手架，切换到 fastmcp/pydantic/jinja2/typer 技术栈"
git push origin main
```

---

### Task 2: 配置层（config.py）

**Files:**
- Create: `src/threedog/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `AppConfig(BaseModel)`: 字段 `db_path: Path`、`output_dir: Path`、`default_strategy: Literal["link","move","copy"] = "link"`
  - `config_dir() -> Path`（环境变量 `THREEDOG_HOME` 优先，否则 `~/.threedog`）
  - `load_config(explicit: Path | None = None) -> AppConfig`（文件缺失时要求字段齐全；加载后自动建目录）
  - `save_config(cfg, path=None) -> Path`（写 TOML）

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

from threedog.config import AppConfig, config_dir, load_config, save_config


def test_config_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("THREEDOG_HOME", str(tmp_path))
    cfg = AppConfig(db_path=tmp_path / "db.sqlite3", output_dir=tmp_path / "out")
    p = save_config(cfg)
    assert p == tmp_path / "config.toml"
    loaded = load_config()
    assert loaded.db_path == cfg.db_path
    assert loaded.default_strategy == "link"
    assert config_dir() == tmp_path


def test_load_creates_dirs(tmp_path: Path):
    cfg = AppConfig(db_path=tmp_path / "a/db.sqlite3", output_dir=tmp_path / "b/out")
    p = save_config(cfg, explicit=tmp_path / "cfg.toml")
    loaded = load_config(explicit=p)
    assert loaded.db_path.parent.exists()
    assert loaded.output_dir.exists()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL（ModuleNotFoundError: threedog.config）

- [ ] **Step 3: 实现 config.py**

```python
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class AppConfig(BaseModel):
    db_path: Path
    output_dir: Path
    default_strategy: Literal["link", "move", "copy"] = "link"


def config_dir() -> Path:
    env = os.environ.get("THREEDOG_HOME")
    return Path(env).expanduser() if env else Path.home() / ".threedog"


def load_config(explicit: Path | None = None) -> AppConfig:
    path = explicit or (config_dir() / "config.toml")
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    cfg = AppConfig(**data)
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    return cfg


def save_config(cfg: AppConfig, explicit: Path | None = None) -> Path:
    path = explicit or (config_dir() / "config.toml")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f'db_path = "{cfg.db_path}"',
        f'output_dir = "{cfg.output_dir}"',
        f'default_strategy = "{cfg.default_strategy}"',
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_config.py -v`
Expected: `2 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/config.py tests/test_config.py
git commit -m "feat: 配置层 AppConfig 与 THREEDOG_HOME 解析"
git push origin main
```

---

### Task 3: 数据库层（db.py + schema.sql）

**Files:**
- Create: `src/threedog/util.py`、`src/threedog/graph/__init__.py`（空）、`src/threedog/graph/schema.sql`、`src/threedog/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces:
  - `utcnow() -> str`（ISO8601 UTC）
  - `Database(path: Path)`：`.conn`（sqlite3.Connection, row_factory=Row）、`.migrate()`、`.close()`；用 `PRAGMA user_version` 做版本迁移
  - 表：files/file_facts/categories/assignments/style_profiles/batches/journal + FTS5 虚表 file_search

- [ ] **Step 1: 写失败测试**

```python
import sqlite3

from threedog.db import Database


def test_migrate_creates_tables(tmp_path):
    db = Database(tmp_path / "t.db")
    names = {
        r["name"]
        for r in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "files", "file_facts", "categories", "assignments",
        "style_profiles", "batches", "journal", "file_search",
    } <= names
    db.close()


def test_migrate_idempotent(tmp_path):
    db = Database(tmp_path / "t.db")
    (v,) = db.conn.execute("PRAGMA user_version").fetchone()
    assert v == 1
    db.close()
    db2 = Database(tmp_path / "t.db")  # 重复打开不报错、版本不变
    (v2,) = db2.conn.execute("PRAGMA user_version").fetchone()
    assert v2 == 1
    db2.close()


def test_util_utcnow():
    from threedog.util import utcnow
    assert utcnow().endswith("+00:00") or "T" in utcnow()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL（ModuleNotFoundError: threedog.db）

- [ ] **Step 3: 实现**

`src/threedog/util.py`:

```python
from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
```

`src/threedog/graph/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  ext TEXT NOT NULL DEFAULT '',
  size INTEGER NOT NULL,
  mtime REAL NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS file_facts(
  file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
  summary TEXT NOT NULL DEFAULT '',
  keywords TEXT NOT NULL DEFAULT '[]',
  extracted_at TEXT
);
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY,
  parent_id INTEGER REFERENCES categories(id),
  style_id INTEGER NOT NULL,
  name_raw TEXT NOT NULL,
  path_raw TEXT NOT NULL,
  sort INTEGER NOT NULL DEFAULT 0,
  narration TEXT,
  UNIQUE(style_id, path_raw)
);
CREATE TABLE IF NOT EXISTS assignments(
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id),
  category_id INTEGER REFERENCES categories(id),
  batch_id TEXT NOT NULL,
  strategy TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS style_profiles(
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  structure TEXT NOT NULL,
  options TEXT NOT NULL,
  naming TEXT NOT NULL,
  presentation TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS batches(
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  plan_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'proposed'
);
CREATE TABLE IF NOT EXISTS journal(
  id INTEGER PRIMARY KEY,
  batch_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  action TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'done',
  created_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS file_search USING fts5(name, summary, keywords);
```

`src/threedog/db.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = (Path(__file__).parent / "graph" / "schema.sql").read_text(encoding="utf-8")
VERSION = 1


class Database:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    def migrate(self) -> None:
        (v,) = self.conn.execute("PRAGMA user_version").fetchone()
        if v < 1:
            self.conn.executescript(SCHEMA)
            self.conn.execute(f"PRAGMA user_version = {VERSION}")
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_db.py -v`
Expected: `3 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/util.py src/threedog/db.py src/threedog/graph tests/test_db.py
git commit -m "feat: SQLite 数据库层与全量 schema（含 FTS5、batches、narration）"
git push origin main
```

---

### Task 4: Store（一）文件表 / 摘要 / FTS5 检索

**Files:**
- Create: `src/threedog/graph/store.py`
- Test: `tests/test_store_files.py`

**Interfaces:**
- Consumes: `Database`、`utcnow()`
- Produces: `Store(db: Database)`，方法：`upsert_file(path,name,ext,size,mtime,now)->int`、`known_files()->dict[str,float]`、`mark_deleted(paths,now)->int`、`get_file(path)->Row|None`、`set_facts(path,summary,keywords,now)`、`get_card(path)->dict`、`search(query,limit=20)->list[dict]`；模块级 `fts_text(s)`、`fts_query(q)`（CJK 逐字切分，解决 unicode61 不切中文的问题）

- [ ] **Step 1: 写失败测试**

```python
import pytest

from threedog.db import Database
from threedog.graph.store import Store
from threedog.util import utcnow


@pytest.fixture()
def store(tmp_path):
    db = Database(tmp_path / "t.db")
    yield Store(db)
    db.close()


def test_upsert_and_known(store):
    now = utcnow()
    fid = store.upsert_file("a/b.txt", "b.txt", "txt", 10, 1.0, now)
    assert store.known_files() == {"a/b.txt": 1.0}
    fid2 = store.upsert_file("a/b.txt", "b.txt", "txt", 20, 2.0, now)
    assert fid2 == fid
    assert store.known_files()["a/b.txt"] == 2.0


def test_facts_card_and_chinese_search(store):
    now = utcnow()
    store.upsert_file("x/报告.md", "报告.md", "md", 5, 1.0, now)
    store.set_facts("x/报告.md", "年度总结", ["总结", "年度"], now)
    card = store.get_card("x/报告.md")
    assert card["summary"] == "年度总结"
    assert card["keywords"] == ["总结", "年度"]
    # 2 个汉字的子串查询必须命中（CJK 逐字切分）
    assert any(h["path"] == "x/报告.md" for h in store.search("总结"))
    # LIKE 兜底：按路径查
    assert any(h["path"] == "x/报告.md" for h in store.search("报告"))


def test_mark_deleted(store):
    now = utcnow()
    store.upsert_file("y/1.log", "1.log", "log", 1, 1.0, now)
    assert store.mark_deleted(["y/1.log"], now) == 1
    assert store.known_files() == {}
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_store_files.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 store.py（文件部分）**

```python
from __future__ import annotations

import json
import re
from typing import Any

from threedog.db import Database

_CJK = re.compile(r"([\u4e00-\u9fff])")


def fts_text(s: str) -> str:
    """CJK 逐字间插空格，让 unicode61 分词器按字建索引。"""
    return _CJK.sub(r" \1 ", s)


def fts_query(q: str) -> str:
    return '"' + " ".join(fts_text(q).split()) + '"'


class Store:
    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    # ---------- files ----------
    def upsert_file(self, path: str, name: str, ext: str,
                    size: int, mtime: float, now: str) -> int:
        self.conn.execute(
            "INSERT INTO files(path,name,ext,size,mtime,first_seen,last_seen,deleted)"
            " VALUES(?,?,?,?,?,?,?,0)"
            " ON CONFLICT(path) DO UPDATE SET size=excluded.size, mtime=excluded.mtime,"
            " last_seen=excluded.last_seen, deleted=0",
            (path, name, ext, size, mtime, now, now))
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM files WHERE path=?", (path,)).fetchone()
        return row["id"]

    def _fts_refresh(self, fid: int, name: str, summary: str = "", keywords: str = "[]") -> None:
        self.conn.execute("DELETE FROM file_search WHERE rowid=?", (fid,))
        self.conn.execute(
            "INSERT INTO file_search(rowid,name,summary,keywords) VALUES(?,?,?,?)",
            (fid, fts_text(name), fts_text(summary), fts_text(keywords)))

    def known_files(self) -> dict[str, float]:
        return {r["path"]: r["mtime"]
                for r in self.conn.execute("SELECT path,mtime FROM files WHERE deleted=0")}

    def mark_deleted(self, paths: list[str], now: str) -> int:
        n = 0
        for p in paths:
            cur = self.conn.execute(
                "UPDATE files SET deleted=1, last_seen=? WHERE path=? AND deleted=0",
                (now, p))
            n += cur.rowcount
        self.conn.commit()
        return n

    def get_file(self, path: str):
        return self.conn.execute("SELECT * FROM files WHERE path=?", (path,)).fetchone()

    # ---------- facts ----------
    def set_facts(self, path: str, summary: str, keywords: list[str], now: str) -> None:
        row = self.get_file(path)
        if row is None:
            raise KeyError(f"not scanned: {path}")
        kw = json.dumps(keywords, ensure_ascii=False)
        self.conn.execute(
            "INSERT INTO file_facts(file_id,summary,keywords,extracted_at) VALUES(?,?,?,?)"
            " ON CONFLICT(file_id) DO UPDATE SET summary=excluded.summary,"
            " keywords=excluded.keywords, extracted_at=excluded.extracted_at",
            (row["id"], summary, kw, now))
        self._fts_refresh(row["id"], row["name"], summary, kw)
        self.conn.commit()

    def get_card(self, path: str) -> dict[str, Any]:
        row = self.get_file(path)
        if row is None:
            raise KeyError(f"not scanned: {path}")
        facts = self.conn.execute(
            "SELECT * FROM file_facts WHERE file_id=?", (row["id"],)).fetchone()
        assigns = self.conn.execute(
            "SELECT a.batch_id, a.strategy, c.path_raw FROM assignments a"
            " JOIN categories c ON c.id = a.category_id"
            " WHERE a.file_id=? AND a.status='active'", (row["id"],)).fetchall()
        return {
            "path": row["path"], "name": row["name"], "ext": row["ext"],
            "size": row["size"], "mtime": row["mtime"],
            "summary": facts["summary"] if facts else "",
            "keywords": json.loads(facts["keywords"]) if facts else [],
            "assignments": [dict(a) for a in assigns],
        }

    # ---------- search ----------
    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        try:
            rows = self.conn.execute(
                "SELECT f.path, f.name, f.ext, f.deleted FROM file_search s"
                " JOIN files f ON f.id = s.rowid"
                " WHERE file_search MATCH ? LIMIT ?",
                (fts_query(query), limit)).fetchall()
        except Exception:
            rows = []
        like = f"%{query}%"
        rows2 = self.conn.execute(
            "SELECT path, name, ext, deleted FROM files"
            " WHERE path LIKE ? AND deleted=0 LIMIT ?", (like, limit)).fetchall()
        merged: dict[str, dict] = {}
        for r in [*rows, *rows2]:
            if not r["deleted"]:
                merged.setdefault(r["path"], dict(r))
        return list(merged.values())
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_store_files.py -v`
Expected: `3 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/graph/store.py tests/test_store_files.py
git commit -m "feat: Store 文件表/摘要/FTS5 中文逐字检索"
git push origin main
```

---

### Task 5: Store（二）风格 / 分类树 / 归类 / 批次 / 账本

**Files:**
- Modify: `src/threedog/graph/store.py`（追加方法）
- Test: `tests/test_store_graph.py`

**Interfaces:**
- Consumes: Task 4 的 `Store`
- Produces（追加到 `Store`）：`save_style(profile:dict)->int`、`set_active_style(id)`、`get_active_style_id()->int|None`、`list_styles()->list[dict]`、`replace_categories(style_id, raw_paths)`、`ensure_category(style_id, raw_path)->int`、`categories_of(style_id)->list[Row]`、`chain_of(style_id, raw_path)->list[Row]`、`set_narration(style_id, raw_path, text)`、`upsert_assignment(path, category_id, batch_id, strategy, now)`、`active_assignment(path)->Row|None`、`revoke_batch(batch_id)`、`files_in_category(category_id)->list[dict]`、`save_batch(batch_id, plan:dict, now, ttl_hours=24)`、`get_batch(batch_id)->Row|None`、`set_batch_status(batch_id, status)`、`append_journal(batch_id, actions:list[dict], now)`、`journal_of(batch_id)->list[Row]`（seq 降序）、`overview()->dict`

- [ ] **Step 1: 写失败测试**

```python
import json

import pytest

from threedog.db import Database
from threedog.graph.store import Store
from threedog.util import utcnow


@pytest.fixture()
def store(tmp_path):
    db = Database(tmp_path / "t.db")
    s = Store(db)
    yield s
    db.close()


def test_style_save_and_activate(store):
    sid = store.save_style({"name": "s1", "structure": "domain",
                            "options": {"domains": ["A"]}, "naming": {},
                            "presentation": {}})
    store.set_active_style(sid)
    assert store.get_active_style_id() == sid
    assert store.list_styles()[0]["name"] == "s1"


def test_categories_tree(store):
    sid = store.save_style({"name": "s1", "structure": "domain",
                            "options": {}, "naming": {}, "presentation": {}})
    store.replace_categories(sid, ["职业发展", "职业发展/证书", "生活"])
    rows = {r["path_raw"]: r for r in store.categories_of(sid)}
    assert rows["职业发展/证书"]["parent_id"] == rows["职业发展"]["id"]
    cid = store.ensure_category(sid, "职业发展/证书")  # 幂等
    assert cid == rows["职业发展/证书"]["id"]
    chain = [r["name_raw"] for r in store.chain_of(sid, "职业发展/证书")]
    assert chain == ["职业发展", "证书"]


def test_assignment_lifecycle(store):
    now = utcnow()
    store.upsert_file("f.txt", "f.txt", "txt", 1, 1.0, now)
    sid = store.save_style({"name": "s1", "structure": "gtd",
                            "options": {}, "naming": {}, "presentation": {}})
    c1 = store.ensure_category(sid, "收件箱")
    c2 = store.ensure_category(sid, "归档")
    store.upsert_assignment("f.txt", c1, "b1", "link", now)
    assert store.active_assignment("f.txt")["category_id"] == c1
    store.upsert_assignment("f.txt", c2, "b2", "link", now)  # 旧的自动 revoke
    assert store.active_assignment("f.txt")["category_id"] == c2
    assert len(store.files_in_category(c1)) == 0
    store.revoke_batch("b2")
    assert store.active_assignment("f.txt") is None


def test_batch_and_journal(store):
    now = utcnow()
    store.save_batch("b1", {"rows": []}, now)
    assert json.loads(store.get_batch("b1")["plan_json"]) == {"rows": []}
    store.append_journal("b1", [{"op": "link", "dst": "x"}], now)
    store.append_journal("b1", [{"op": "link", "dst": "y"}], now)
    assert [json.loads(r["action"])["dst"] for r in store.journal_of("b1")] == ["y", "x"]
    store.set_batch_status("b1", "applied")
    assert store.get_batch("b1")["status"] == "applied"


def test_overview(store):
    now = utcnow()
    store.upsert_file("a.txt", "a.txt", "txt", 1, 1.0, now)
    store.upsert_file("b.txt", "b.txt", "txt", 1, 1.0, now)
    ov = store.overview()
    assert ov["files"] == 2 and ov["unassigned"] == 2
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_store_graph.py -v`
Expected: FAIL（AttributeError: save_style）

- [ ] **Step 3: 在 Store 类中追加实现**

```python
    # ---------- styles ----------
    def save_style(self, profile: dict) -> int:
        self.conn.execute(
            "INSERT INTO style_profiles(name,structure,options,naming,presentation,active)"
            " VALUES(?,?,?,?,?,?)"
            " ON CONFLICT(name) DO UPDATE SET structure=excluded.structure,"
            " options=excluded.options, naming=excluded.naming,"
            " presentation=excluded.presentation",
            (profile["name"], profile["structure"],
             json.dumps(profile["options"], ensure_ascii=False),
             json.dumps(profile["naming"], ensure_ascii=False),
             json.dumps(profile["presentation"], ensure_ascii=False),
             profile.get("active", 0)))
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM style_profiles WHERE name=?", (profile["name"],)).fetchone()
        return row["id"]

    def set_active_style(self, style_id: int) -> None:
        self.conn.execute("UPDATE style_profiles SET active=0 WHERE active=1")
        self.conn.execute("UPDATE style_profiles SET active=1 WHERE id=?", (style_id,))
        self.conn.commit()

    def get_active_style_id(self) -> int | None:
        row = self.conn.execute(
            "SELECT id FROM style_profiles WHERE active=1").fetchone()
        return row["id"] if row else None

    def list_styles(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT id,name,structure,active FROM style_profiles ORDER BY id")]

    # ---------- categories ----------
    def replace_categories(self, style_id: int, raw_paths: list[str]) -> None:
        self.conn.execute("DELETE FROM categories WHERE style_id=?", (style_id,))
        for p in sorted(raw_paths):
            parts = p.split("/")
            parent = None
            for depth, name in enumerate(parts):
                prefix = "/".join(parts[: depth + 1])
                row = self.conn.execute(
                    "SELECT id FROM categories WHERE style_id=? AND path_raw=?",
                    (style_id, prefix)).fetchone()
                if row is None:
                    sort = self.conn.execute(
                        "SELECT COALESCE(MAX(sort),0)+1 FROM categories"
                        " WHERE style_id=? AND parent_id IS ?",
                        (style_id, parent)).fetchone()[0]
                    parent = self.conn.execute(
                        "INSERT INTO categories(style_id,parent_id,name_raw,path_raw,sort)"
                        " VALUES(?,?,?,?,?)",
                        (style_id, parent, name, prefix, sort)).lastrowid
                else:
                    parent = row["id"]
        self.conn.commit()

    def ensure_category(self, style_id: int, raw_path: str) -> int:
        self.replace_categories(style_id, [raw_path])
        return self.conn.execute(
            "SELECT id FROM categories WHERE style_id=? AND path_raw=?",
            (style_id, raw_path)).fetchone()["id"]

    def categories_of(self, style_id: int) -> list:
        return self.conn.execute(
            "SELECT * FROM categories WHERE style_id=?"
            " ORDER BY parent_id IS NULL DESC, sort", (style_id,)).fetchall()

    def chain_of(self, style_id: int, raw_path: str) -> list:
        parts = raw_path.split("/")
        rows = []
        for i in range(1, len(parts) + 1):
            r = self.conn.execute(
                "SELECT * FROM categories WHERE style_id=? AND path_raw=?",
                (style_id, "/".join(parts[:i]))).fetchone()
            if r is not None:
                rows.append(r)
        return rows

    def set_narration(self, style_id: int, raw_path: str, text: str) -> None:
        self.conn.execute(
            "UPDATE categories SET narration=? WHERE style_id=? AND path_raw=?",
            (text, style_id, raw_path))
        self.conn.commit()

    # ---------- assignments ----------
    def upsert_assignment(self, path: str, category_id: int, batch_id: str,
                          strategy: str, now: str) -> None:
        row = self.get_file(path)
        self.conn.execute(
            "UPDATE assignments SET status='revoked' WHERE file_id=? AND status='active'",
            (row["id"],))
        self.conn.execute(
            "INSERT INTO assignments(file_id,category_id,batch_id,strategy,status,created_at)"
            " VALUES(?,?,?,?, 'active', ?)",
            (row["id"], category_id, batch_id, strategy, now))
        self.conn.commit()

    def active_assignment(self, path: str):
        row = self.get_file(path)
        return self.conn.execute(
            "SELECT * FROM assignments WHERE file_id=? AND status='active'",
            (row["id"],)).fetchone()

    def revoke_batch(self, batch_id: str) -> None:
        self.conn.execute(
            "UPDATE assignments SET status='revoked' WHERE batch_id=? AND status='active'",
            (batch_id,))
        self.conn.commit()

    def files_in_category(self, category_id: int) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT f.path, f.name, f.size, f.mtime FROM assignments a"
            " JOIN files f ON f.id = a.file_id"
            " WHERE a.category_id=? AND a.status='active' AND f.deleted=0",
            (category_id,))]

    # ---------- batches / journal ----------
    def save_batch(self, batch_id: str, plan: dict, now: str, ttl_hours: int = 24) -> None:
        from datetime import datetime, timedelta
        expires = (datetime.fromisoformat(now)
                   + timedelta(hours=ttl_hours)).isoformat()
        self.conn.execute(
            "INSERT OR REPLACE INTO batches(id,created_at,expires_at,plan_json,status)"
            " VALUES(?,?,?,?, 'proposed')",
            (batch_id, now, expires, json.dumps(plan, ensure_ascii=False)))
        self.conn.commit()

    def get_batch(self, batch_id: str):
        return self.conn.execute(
            "SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()

    def set_batch_status(self, batch_id: str, status: str) -> None:
        self.conn.execute(
            "UPDATE batches SET status=? WHERE id=?", (status, batch_id))
        self.conn.commit()

    def append_journal(self, batch_id: str, actions: list[dict], now: str) -> None:
        for i, a in enumerate(actions):
            self.conn.execute(
                "INSERT INTO journal(batch_id,seq,action,status,created_at)"
                " VALUES(?,?,?, 'done', ?)",
                (batch_id, i, json.dumps(a, ensure_ascii=False), now))
        self.conn.commit()

    def journal_of(self, batch_id: str) -> list:
        return self.conn.execute(
            "SELECT * FROM journal WHERE batch_id=? ORDER BY seq DESC",
            (batch_id,)).fetchall()

    # ---------- overview ----------
    def overview(self) -> dict:
        def one(sql: str) -> int:
            return self.conn.execute(sql).fetchone()[0]

        return {
            "files": one("SELECT COUNT(*) FROM files WHERE deleted=0"),
            "unassigned": one(
                "SELECT COUNT(*) FROM files f WHERE f.deleted=0 AND NOT EXISTS"
                " (SELECT 1 FROM assignments a"
                "  WHERE a.file_id=f.id AND a.status='active')"),
            "styles": self.list_styles(),
            "active_style": self.get_active_style_id(),
            "recent_batches": [dict(r) for r in self.conn.execute(
                "SELECT id,status,created_at FROM batches"
                " ORDER BY created_at DESC LIMIT 5")],
        }
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_store_graph.py -v`
Expected: `5 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/graph/store.py tests/test_store_graph.py
git commit -m "feat: Store 风格/分类树/归类/批次/账本"
git push origin main
```

---

### Task 6: 扫描器（walker + incremental）

**Files:**
- Create: `src/threedog/scan/__init__.py`（空）、`src/threedog/scan/walker.py`、`src/threedog/scan/incremental.py`
- Test: `tests/test_scan.py`

**Interfaces:**
- Consumes: `Store`、`utcnow()`
- Produces:
  - `FileMeta(path:str, name:str, ext:str, size:int, mtime:float)`
  - `walk(root: Path) -> list[FileMeta]`（跳过隐藏目录/`.git`/`.venv`/`node_modules`/`__pycache__`/回收站；跳过符号链接文件）
  - `ScanDiff(new, changed, deleted)`、`diff(store, metas, now=None) -> ScanDiff`（同时把结果写回库）

- [ ] **Step 1: 写失败测试**

```python
from threedog.db import Database
from threedog.graph.store import Store
from threedog.scan.incremental import diff
from threedog.scan.walker import walk
from threedog.util import utcnow


def test_walk_skips_hidden_and_links(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    f = tmp_path / "sub" / "a.txt"
    f.write_text("hello")
    metas = walk(tmp_path)
    assert [m.name for m in metas] == ["a.txt"]
    assert metas[0].ext == "txt" and metas[0].size == 5


def test_diff_incremental(tmp_path):
    db = Database(tmp_path / "t.db")
    store = Store(db)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("1")

    d1 = diff(store, walk(src))
    assert [m.name for m in d1.new] == ["a.txt"] and not d1.deleted

    d2 = diff(store, walk(src))          # 第二遍无变化
    assert not d2.new and not d2.changed and not d2.deleted

    (src / "a.txt").write_text("changed content")
    d3 = diff(store, walk(src))
    assert [m.name for m in d3.changed] == ["a.txt"]

    (src / "a.txt").unlink()
    d4 = diff(store, walk(src))
    assert len(d4.deleted) == 1
    db.close()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_scan.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`src/threedog/scan/walker.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__",
             "$RECYCLE.BIN", "System Volume Information", ".threedog"}


@dataclass
class FileMeta:
    path: str
    name: str
    ext: str
    size: int
    mtime: float


def walk(root: Path) -> list[FileMeta]:
    metas: list[FileMeta] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            fp = Path(dirpath) / fn
            if fp.is_symlink():
                continue
            st = fp.stat()
            metas.append(FileMeta(str(fp), fn, fp.suffix.lstrip(".").lower(),
                                  st.st_size, st.st_mtime))
    return metas
```

`src/threedog/scan/incremental.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from threedog.graph.store import Store
from threedog.scan.walker import FileMeta
from threedog.util import utcnow


@dataclass
class ScanDiff:
    new: list[FileMeta] = field(default_factory=list)
    changed: list[FileMeta] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)


def diff(store: Store, metas: list[FileMeta], now: str | None = None) -> ScanDiff:
    now = now or utcnow()
    known = store.known_files()
    result = ScanDiff()
    seen: set[str] = set()
    for m in metas:
        seen.add(m.path)
        if m.path not in known:
            result.new.append(m)
            store.upsert_file(m.path, m.name, m.ext, m.size, m.mtime, now)
        elif known[m.path] != m.mtime:
            result.changed.append(m)
            store.upsert_file(m.path, m.name, m.ext, m.size, m.mtime, now)
    result.deleted = [p for p in known if p not in seen]
    store.mark_deleted(result.deleted, now)
    return result
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_scan.py -v`
Expected: `2 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/scan tests/test_scan.py
git commit -m "feat: 目录扫描器与增量 diff"
git push origin main
```

---

### Task 7: 风格档案模型（style/profile.py）

**Files:**
- Create: `src/threedog/style/__init__.py`（空）、`src/threedog/style/profile.py`
- Test: `tests/test_profile.py`

**Interfaces:**
- Produces:
  - `StructureOptions(domains:list[str]=[], projects:list[str]=[], granularity:Literal["year","quarter","month"]="month", inbox:bool=True)`
  - `NamingSpec(convention:Literal["zh","bilingual","emoji","numbered"]="zh", emoji_map:dict={}, en_map:dict={}, number_width:int=2)`
  - `Presentation(portal:Literal["minimal","dashboard","timeline"]="minimal", show_stats=True, narration=True)`
  - `StyleProfile(id:int|None=None, name:str, structure:Literal["domain","project","time","gtd"], options, naming, presentation, active:bool=False)`；校验：domain⇒domains 非空，project⇒projects 非空

- [ ] **Step 1: 写失败测试**

```python
import pytest
from pydantic import ValidationError

from threedog.style.profile import StyleProfile


def test_defaults():
    p = StyleProfile(name="s", structure="gtd")
    assert p.naming.convention == "zh"
    assert p.presentation.portal == "minimal"
    assert p.options.inbox is True


def test_domain_requires_domains():
    with pytest.raises(ValidationError):
        StyleProfile(name="s", structure="domain")


def test_full_profile():
    p = StyleProfile(name="工作台", structure="domain",
                     options={"domains": ["职业发展"], "inbox": False},
                     naming={"convention": "emoji",
                             "emoji_map": {"职业发展": "💼"}},
                     presentation={"portal": "dashboard"})
    assert p.naming.emoji_map["职业发展"] == "💼"
    assert p.options.inbox is False
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_profile.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 profile.py**

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class StructureOptions(BaseModel):
    domains: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    granularity: Literal["year", "quarter", "month"] = "month"
    inbox: bool = True


class NamingSpec(BaseModel):
    convention: Literal["zh", "bilingual", "emoji", "numbered"] = "zh"
    emoji_map: dict[str, str] = Field(default_factory=dict)
    en_map: dict[str, str] = Field(default_factory=dict)
    number_width: int = 2


class Presentation(BaseModel):
    portal: Literal["minimal", "dashboard", "timeline"] = "minimal"
    show_stats: bool = True
    narration: bool = True


class StyleProfile(BaseModel):
    id: int | None = None
    name: str
    structure: Literal["domain", "project", "time", "gtd"]
    options: StructureOptions = Field(default_factory=StructureOptions)
    naming: NamingSpec = Field(default_factory=NamingSpec)
    presentation: Presentation = Field(default_factory=Presentation)
    active: bool = False

    @model_validator(mode="after")
    def _check(self) -> "StyleProfile":
        if self.structure == "domain" and not self.options.domains:
            raise ValueError("domain 结构需要 options.domains 非空")
        if self.structure == "project" and not self.options.projects:
            raise ValueError("project 结构需要 options.projects 非空")
        return self
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_profile.py -v`
Expected: `3 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/style tests/test_profile.py
git commit -m "feat: 风格档案 pydantic 模型（结构/命名/呈现）"
git push origin main
```

---

### Task 8: 命名规则（style/naming.py）

**Files:**
- Create: `src/threedog/style/naming.py`
- Test: `tests/test_naming.py`

**Interfaces:**
- Consumes: `NamingSpec`
- Produces: `sanitize(name:str)->str`（NFC、去非法字符 `<>:"/\|?*`、去尾部点/空格、Windows 保留名前缀 `_`、空名兜底 `_`）；`display_name(name_raw:str, naming:NamingSpec, index:int=0)->str`

- [ ] **Step 1: 写失败测试**

```python
from threedog.style.naming import display_name, sanitize
from threedog.style.profile import NamingSpec


def test_sanitize():
    assert sanitize("a<b>:c") == "abc"
    assert sanitize("CON") == "_CON"
    assert sanitize("目录. ") == "目录"
    assert sanitize("///") == "_"


def test_conventions():
    assert display_name("职业发展", NamingSpec()) == "职业发展"
    emo = NamingSpec(convention="emoji", emoji_map={"职业发展": "💼"})
    assert display_name("职业发展", emo) == "💼职业发展"
    assert display_name("未知", emo) == "📁未知"
    num = NamingSpec(convention="numbered")
    assert display_name("生活", num, index=2) == "02-生活"
    bi = NamingSpec(convention="bilingual", en_map={"职业发展": "Career"})
    assert display_name("职业发展", bi) == "Career-职业发展"
    assert display_name("生活", bi) == "生活"  # 无映射时原样
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_naming.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 naming.py**

```python
from __future__ import annotations

import unicodedata

from threedog.style.profile import NamingSpec

INVALID = '<>:"/\\|?*'
RESERVED = {"CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10))}


def sanitize(name: str) -> str:
    name = unicodedata.normalize("NFC", name)
    name = "".join(c for c in name if c not in INVALID).strip().rstrip(". ")
    if name.upper() in RESERVED:
        name = "_" + name
    return name or "_"


def display_name(name_raw: str, naming: NamingSpec, index: int = 0) -> str:
    n = sanitize(name_raw)
    if naming.convention == "emoji":
        return f"{naming.emoji_map.get(name_raw, '📁')}{n}"
    if naming.convention == "numbered":
        return f"{index:0{naming.number_width}d}-{n}"
    if naming.convention == "bilingual":
        en = naming.en_map.get(name_raw)
        return f"{en}-{n}" if en else n
    return n
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_naming.py -v`
Expected: `2 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/style/naming.py tests/test_naming.py
git commit -m "feat: 命名规则（zh/bilingual/emoji/numbered + Windows 清洗）"
git push origin main
```

---

### Task 9: 结构骨架（style/skeleton.py）

**Files:**
- Create: `src/threedog/style/skeleton.py`
- Test: `tests/test_skeleton.py`

**Interfaces:**
- Consumes: `StyleProfile`
- Produces:
  - `CategoryNode(name_raw:str, children:list[CategoryNode]=[])`
  - `build_skeleton(profile: StyleProfile) -> list[CategoryNode]`：gtd→[收件箱,下一步,资料,归档]；domain→domains；project→projects；time→granularity 对应当前期节点（`2026` / `2026Q3` / `2026-08`）；全部结构在 `options.inbox=True` 时头部插入 `待整理`
  - `flatten(nodes) -> list[str]`（含中间路径的 raw path 列表）

- [ ] **Step 1: 写失败测试**

```python
from threedog.style.profile import StyleProfile
from threedog.style.skeleton import CategoryNode, build_skeleton, flatten


def test_gtd_with_inbox():
    p = StyleProfile(name="s", structure="gtd")
    names = [n.name_raw for n in build_skeleton(p)]
    assert names == ["待整理", "收件箱", "下一步", "资料", "归档"]


def test_domain_without_inbox():
    p = StyleProfile(name="s", structure="domain",
                     options={"domains": ["职业发展", "生活"], "inbox": False})
    assert [n.name_raw for n in build_skeleton(p)] == ["职业发展", "生活"]


def test_project():
    p = StyleProfile(name="s", structure="project",
                     options={"projects": ["装修", "跳槽"], "inbox": False})
    assert [n.name_raw for n in build_skeleton(p)] == ["装修", "跳槽"]


def test_time_month():
    p = StyleProfile(name="s", structure="time", options={"inbox": False})
    (node,) = build_skeleton(p)
    assert node.name_raw.count("-") == 1  # 2026-08 形态


def test_flatten():
    root = CategoryNode("A", [CategoryNode("B", [CategoryNode("C")])])
    assert flatten([root]) == ["A", "A/B", "A/B/C"]
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_skeleton.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 skeleton.py**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from threedog.style.profile import StyleProfile


@dataclass
class CategoryNode:
    name_raw: str
    children: list["CategoryNode"] = field(default_factory=list)


def build_skeleton(profile: StyleProfile) -> list[CategoryNode]:
    o = profile.options
    if profile.structure == "gtd":
        names = ["收件箱", "下一步", "资料", "归档"]
    elif profile.structure == "time":
        t = date.today()
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
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_skeleton.py -v`
Expected: `5 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/style/skeleton.py tests/test_skeleton.py
git commit -m "feat: 结构骨架生成（domain/project/time/gtd + 收件箱）"
git push origin main
```

---

### Task 10: 门户渲染器（style/renderers）

**Files:**
- Create: `src/threedog/style/renderers/__init__.py`、`src/threedog/style/renderers/markdown.py`
- Test: `tests/test_renderers.py`

**Interfaces:**
- Consumes: `Presentation`
- Produces:
  - `Renderer`（抽象基类，方法 `render_index(title:str, files:list[dict], stats:dict, narration:str|None) -> str`）——v2 HTML 渲染器实现此基类
  - `get_renderer(p: Presentation) -> Renderer`（按 `portal` 返回 minimal/dashboard/timeline 版式）

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_renderers.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`src/threedog/style/renderers/__init__.py`:

```python
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
```

`src/threedog/style/renderers/markdown.py`:

```python
from __future__ import annotations

from datetime import datetime
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
    return datetime.fromtimestamp(mtime).strftime("%Y-%m")


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
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_renderers.py -v`
Expected: `3 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/style/renderers tests/test_renderers.py
git commit -m "feat: Markdown 门户渲染器（minimal/dashboard/timeline）"
git push origin main
```

---

### Task 11: 写操作策略（actions/strategies.py）

**Files:**
- Create: `src/threedog/actions/__init__.py`（空）、`src/threedog/actions/strategies.py`
- Test: `tests/test_strategies.py`

**Interfaces:**
- Produces:
  - `long_path(p: Path) -> str`（Windows >240 字符加 `\\?\` 前缀）
  - `symlink_ok() -> bool`（临时目录探测，结果缓存）
  - `Strategy`（抽象）：`name:str`、`execute(src:Path, dst:Path) -> str`（返回 rollback_info）、`rollback(dst:Path, info:str)`
  - `LinkStrategy` / `MoveStrategy` / `CopyStrategy`、`get_strategy(name:str) -> Strategy`

- [ ] **Step 1: 写失败测试**

```python
import pytest

from threedog.actions.strategies import LinkStrategy, get_strategy, symlink_ok


@pytest.mark.parametrize("name", ["copy", "move", "link"])
def test_execute_and_rollback(name, tmp_path):
    if name == "link":
        pytest.mark.skipif(not symlink_ok(), reason="无软链权限")()
    src = tmp_path / "s.txt"
    src.write_text("data")
    dst = tmp_path / "out" / "d.txt"
    strat = get_strategy(name)
    info = strat.execute(src, dst)
    assert dst.exists() and dst.read_text() == "data"
    if name == "move":
        assert not src.exists()
    strat.rollback(dst, info)
    assert not dst.exists()
    if name == "move":
        assert src.exists() and src.read_text() == "data"
    if name == "link":
        assert src.exists()


def test_link_strategy_is_symlink(tmp_path):
    if not symlink_ok():
        pytest.skip("无软链权限")
    src = tmp_path / "s.txt"
    src.write_text("x")
    dst = tmp_path / "d.txt"
    LinkStrategy().execute(src, dst)
    assert dst.is_symlink()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_strategies.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 strategies.py**

```python
from __future__ import annotations

import os
import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path


def long_path(p: Path) -> str:
    s = str(p)
    if os.name == "nt" and not s.startswith("\\\\?\\") and len(s) > 240:
        return "\\\\?\\" + s
    return s


_symlink_ok: bool | None = None


def symlink_ok() -> bool:
    global _symlink_ok
    if _symlink_ok is None:
        try:
            with tempfile.TemporaryDirectory() as td:
                src = Path(td) / "s.txt"
                src.write_text("x", encoding="utf-8")
                dst = Path(td) / "d.txt"
                os.symlink(long_path(src), long_path(dst))
            _symlink_ok = True
        except OSError:
            _symlink_ok = False
    return _symlink_ok


class Strategy(ABC):
    name: str

    @abstractmethod
    def execute(self, src: Path, dst: Path) -> str: ...

    @abstractmethod
    def rollback(self, dst: Path, info: str) -> None: ...


class LinkStrategy(Strategy):
    name = "link"

    def execute(self, src: Path, dst: Path) -> str:
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(long_path(src), long_path(dst))
        return str(src)

    def rollback(self, dst: Path, info: str) -> None:
        if dst.is_symlink() or dst.exists():
            dst.unlink()


class MoveStrategy(Strategy):
    name = "move"

    def execute(self, src: Path, dst: Path) -> str:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(long_path(src), long_path(dst))
        return str(src)

    def rollback(self, dst: Path, info: str) -> None:
        orig = Path(info)
        orig.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(long_path(dst), long_path(orig))


class CopyStrategy(Strategy):
    name = "copy"

    def execute(self, src: Path, dst: Path) -> str:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(long_path(src), long_path(dst))
        return ""

    def rollback(self, dst: Path, info: str) -> None:
        if dst.exists():
            dst.unlink()


def get_strategy(name: str) -> Strategy:
    return {"link": LinkStrategy, "move": MoveStrategy, "copy": CopyStrategy}[name]()
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_strategies.py -v`
Expected: `4 passed`（无软链权限时 3 passed + 1 skipped）

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/actions tests/test_strategies.py
git commit -m "feat: link/move/copy 写策略与回滚、长路径、软链探测"
git push origin main
```

---

### Task 12: 流水线（actions/pipeline.py）

**Files:**
- Create: `src/threedog/actions/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `Store`、`AppConfig`、`display_name`、`build_skeleton/flatten`、`get_renderer`、`get_strategy/symlink_ok`
- Produces: `Pipeline(store, config)`：
  - `active_profile()->StyleProfile`、`profile_by_id(style_id)->StyleProfile`
  - `activate_style(style_id)`：激活风格 + 重建骨架（保留已有 narration）
  - `propose(pairs: list[tuple[src,raw_cat]], strategy=None) -> dict`（plan：batch_id/strategy/rows[status: ready|already|conflict|unknown_file]，存批次 24h）
  - `apply(batch_id) -> dict`（校验过期/stale/软链权限；逐条执行+账本+归类+渲染 INDEX.md；返回 ok/failed/skipped；单条失败不中断）
  - `rollback(batch_id) -> dict`（账本逆序还原、revoke 归类、删 INDEX.md、清空目录）
  - `write_portal(raw_cat, markdown) -> str`（写 narration 并重渲染，返回 INDEX.md 路径）

- [ ] **Step 1: 写失败测试**

```python
import pytest

from threedog.actions.pipeline import Pipeline
from threedog.actions.strategies import symlink_ok
from threedog.config import AppConfig
from threedog.db import Database
from threedog.graph.store import Store
from threedog.scan.incremental import diff
from threedog.scan.walker import walk
from threedog.util import utcnow

STRAT = "link" if symlink_ok() else "copy"


@pytest.fixture()
def env(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"
    (src / "a.txt").write_text("a")
    (src / "b.txt").write_text("b")
    db = Database(tmp_path / "t.db")
    store = Store(db)
    cfg = AppConfig(db_path=tmp_path / "t.db", output_dir=out, default_strategy=STRAT)
    pipe = Pipeline(store, cfg)
    diff(store, walk(src))
    sid = store.save_style({"name": "s", "structure": "gtd", "options": {},
                            "naming": {}, "presentation": {"portal": "minimal"}})
    pipe.activate_style(sid)
    yield store, pipe, src, out
    db.close()


def test_full_flow(env):
    store, pipe, src, out = env
    a, b = str(src / "a.txt"), str(src / "b.txt")
    plan = pipe.propose([(a, "收件箱"), (b, "归档")], strategy=STRAT)
    assert all(r["status"] == "ready" for r in plan["rows"])
    res = pipe.apply(plan["batch_id"])
    assert sorted(res["ok"]) == [a, b] and not res["failed"]
    assert (out / "收件箱" / "a.txt").exists()
    assert (out / "收件箱" / "INDEX.md").exists()
    assert store.active_assignment(a)["batch_id"] == plan["batch_id"]

    r = pipe.rollback(plan["batch_id"])
    assert len(r["restored"]) == 2
    assert not (out / "收件箱" / "a.txt").exists()
    assert store.active_assignment(a) is None


def test_conflict_unknown_stale(env):
    store, pipe, src, out = env
    (out / "收件箱").mkdir(parents=True)
    (out / "收件箱" / "a.txt").write_text("占位")
    plan = pipe.propose([(str(src / "a.txt"), "收件箱"),
                         (str(src / "nope.txt"), "归档")], strategy=STRAT)
    by = {r["src"]: r["status"] for r in plan["rows"]}
    assert by[str(src / "a.txt")] == "conflict"
    assert by[str(src / "nope.txt")] == "unknown_file"
    res = pipe.apply(plan["batch_id"])
    assert res["ok"] == [] and len(res["skipped"]) == 2


def test_expired_batch(env):
    store, pipe, _src, _out = env
    store.save_batch("dead", {"strategy": "copy", "rows": []}, utcnow(), ttl_hours=0)
    with pytest.raises(RuntimeError, match="过期"):
        pipe.apply("dead")


def test_write_portal(env):
    _store, pipe, src, out = env
    a = str(src / "a.txt")
    plan = pipe.propose([(a, "归档")], strategy=STRAT)
    pipe.apply(plan["batch_id"])
    pipe.write_portal("归档", "这是归档导读。")
    content = (out / "归档" / "INDEX.md").read_text(encoding="utf-8")
    assert "这是归档导读。" in content and "a.txt" in content
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 pipeline.py**

```python
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from threedog.actions.strategies import get_strategy, symlink_ok
from threedog.config import AppConfig
from threedog.graph.store import Store
from threedog.style.naming import display_name
from threedog.style.profile import StyleProfile
from threedog.style.renderers import get_renderer
from threedog.style.skeleton import build_skeleton, flatten
from threedog.util import utcnow


class Pipeline:
    def __init__(self, store: Store, config: AppConfig):
        self.store = store
        self.config = config

    # ---------- style ----------
    def profile_by_id(self, style_id: int) -> StyleProfile:
        row = self.store.conn.execute(
            "SELECT * FROM style_profiles WHERE id=?", (style_id,)).fetchone()
        return StyleProfile(id=row["id"], name=row["name"], structure=row["structure"],
                            options=json.loads(row["options"]),
                            naming=json.loads(row["naming"]),
                            presentation=json.loads(row["presentation"]))

    def active_profile(self) -> StyleProfile:
        sid = self.store.get_active_style_id()
        if sid is None:
            raise RuntimeError("没有激活的风格档案，请先 create_style + set_active_style")
        return self.profile_by_id(sid)

    def activate_style(self, style_id: int) -> dict:
        kept = {r["path_raw"]: r["narration"]
                for r in self.store.categories_of(style_id) if r["narration"]}
        profile = self.profile_by_id(style_id)
        self.store.set_active_style(style_id)
        self.store.replace_categories(style_id, flatten(build_skeleton(profile)))
        for path_raw, text in kept.items():
            self.store.set_narration(style_id, path_raw, text)
        return {"active_style": style_id}

    # ---------- display ----------
    def _display_chain(self, profile: StyleProfile, raw_path: str) -> list[str]:
        parts = [p for p in raw_path.split("/") if p]
        chain: list[str] = []
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            row = self.store.conn.execute(
                "SELECT name_raw, sort FROM categories WHERE style_id=? AND path_raw=?",
                (profile.id, prefix)).fetchone()
            raw = row["name_raw"] if row else parts[i - 1]
            idx = row["sort"] if row else 0
            chain.append(display_name(raw, profile.naming, idx))
        return chain

    def _cat_dir(self, profile: StyleProfile, raw_path: str) -> Path:
        return self.config.output_dir.joinpath(*self._display_chain(profile, raw_path))

    # ---------- portal ----------
    def _render_portal(self, profile: StyleProfile, raw_path: str) -> None:
        row = self.store.conn.execute(
            "SELECT id, narration FROM categories WHERE style_id=? AND path_raw=?",
            (profile.id, raw_path)).fetchone()
        files = self.store.files_in_category(row["id"])
        stats = {"total": len(files), "size": sum(f["size"] for f in files)}
        content = get_renderer(profile.presentation).render_index(
            title="/".join(self._display_chain(profile, raw_path)),
            files=files, stats=stats,
            narration=row["narration"] if profile.presentation.narration else None)
        cat_dir = self._cat_dir(profile, raw_path)
        cat_dir.mkdir(parents=True, exist_ok=True)
        (cat_dir / "INDEX.md").write_text(content, encoding="utf-8")

    def write_portal(self, raw_cat: str, markdown: str) -> str:
        profile = self.active_profile()
        self.store.ensure_category(profile.id, raw_cat)
        self.store.set_narration(profile.id, raw_cat, markdown)
        self._render_portal(profile, raw_cat)
        return str(self._cat_dir(profile, raw_cat) / "INDEX.md")

    # ---------- pipeline ----------
    def propose(self, pairs: list[tuple[str, str]], strategy: str | None = None) -> dict:
        strat_name = strategy or self.config.default_strategy
        profile = self.active_profile()
        batch_id = uuid.uuid4().hex[:12]
        rows: list[dict[str, Any]] = []
        for src, raw_cat in pairs:
            meta = self.store.get_file(src)
            if meta is None:
                rows.append({"src": src, "category": raw_cat, "status": "unknown_file"})
                continue
            dst = self._cat_dir(profile, raw_cat) / meta["name"]
            if dst.is_symlink() and str(dst.resolve()) == str(Path(src).resolve()):
                status = "already"
            elif dst.exists():
                status = "conflict"
            else:
                status = "ready"
            rows.append({"src": src, "category": raw_cat,
                         "dst": str(dst), "status": status})
        plan = {"batch_id": batch_id, "strategy": strat_name, "rows": rows}
        self.store.save_batch(batch_id, plan, utcnow())
        return plan

    def apply(self, batch_id: str) -> dict:
        b = self.store.get_batch(batch_id)
        if b is None:
            raise KeyError(f"batch 不存在: {batch_id}")
        if b["status"] != "proposed":
            raise RuntimeError(f"batch 状态为 {b['status']}，不能 apply")
        expires = datetime.fromisoformat(b["expires_at"])
        if expires <= datetime.now(expires.tzinfo):
            self.store.set_batch_status(batch_id, "expired")
            raise RuntimeError("preview 已过期（24h），请重新 propose")
        plan = json.loads(b["plan_json"])
        strat_name = plan["strategy"]
        if strat_name == "link" and not symlink_ok():
            raise RuntimeError("当前环境无软链权限（Windows 需开发者模式），"
                               "请用 copy/move 策略重新 propose")
        strat = get_strategy(strat_name)
        profile = self.active_profile()
        ok: list[str] = []
        failed: list[dict] = []
        skipped: list[str] = []
        journal: list[dict] = []
        affected: set[str] = set()
        for row in plan["rows"]:
            if row["status"] != "ready":
                skipped.append(row["src"])
                continue
            src = Path(row["src"])
            meta = self.store.get_file(row["src"])
            if not src.exists() or src.stat().st_mtime != meta["mtime"]:
                skipped.append(row["src"])  # stale：preview 后源文件变动
                continue
            try:
                info = strat.execute(src, Path(row["dst"]))
                cid = self.store.ensure_category(profile.id, row["category"])
                journal.append({"op": strat_name, "src": str(src), "dst": row["dst"],
                                "rollback_info": info, "category": row["category"]})
                self.store.upsert_assignment(row["src"], cid, batch_id,
                                             strat_name, utcnow())
                affected.add(row["category"])
                ok.append(row["src"])
            except OSError as e:
                failed.append({"src": row["src"], "error": str(e)})
        if journal:
            self.store.append_journal(batch_id, journal, utcnow())
        for raw_cat in affected:
            self._render_portal(profile, raw_cat)
        self.store.set_batch_status(batch_id, "partial" if failed else "applied")
        return {"ok": ok, "failed": failed, "skipped": skipped}

    def rollback(self, batch_id: str) -> dict:
        entries = self.store.journal_of(batch_id)  # seq 降序 = 执行逆序
        if not entries:
            raise KeyError(f"batch 无账本记录: {batch_id}")
        restored: list[str] = []
        failed: list[dict] = []
        cats: set[str] = set()
        for e in entries:
            a = json.loads(e["action"])
            try:
                get_strategy(a["op"]).rollback(Path(a["dst"]), a["rollback_info"])
                restored.append(a["dst"])
            except OSError as ex:
                failed.append({"dst": a["dst"], "error": str(ex)})
            cats.add(a["category"])
        self.store.revoke_batch(batch_id)
        profile = self.active_profile()
        for raw_cat in cats:
            idx = self._cat_dir(profile, raw_cat) / "INDEX.md"
            if idx.exists():
                idx.unlink()
        dirs = sorted({self._cat_dir(profile, c) for c in cats},
                      key=lambda p: len(p.parts), reverse=True)
        for d in dirs:
            for sub in sorted(d.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if sub.is_dir():
                    try:
                        sub.rmdir()
                    except OSError:
                        pass
            try:
                d.rmdir()
            except OSError:
                pass
        self.store.set_batch_status(batch_id, "rolled_back")
        return {"restored": restored, "failed": failed}
```

（注：`import os` 若 ruff 报未使用则删除。）

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: `4 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/actions/pipeline.py tests/test_pipeline.py
git commit -m "feat: preview→apply→rollback 写操作流水线"
git push origin main
```

---

### Task 13: MCP server（server.py）

**Files:**
- Create: `src/threedog/server.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `Store`、`Pipeline`（含公开方法 `active_profile()`、`profile_by_id(style_id)`、`activate_style`、`propose/apply/rollback/write_portal`）、`walk/diff`、`build_skeleton/flatten`、`display_name`、`StyleProfile`
- Produces: 模块级 `mcp: FastMCP`（13 个工具 + 3 个 prompt）、`services()->(Store,Pipeline,AppConfig)`（惰性单例）、`reset()`（测试重置）

**Spec 偏差（2 处，均已确认合理）：** `scan` 省略 `incremental` 参数（diff 语义恒为增量）；新增 `set_file_facts` 工具（spec §4 要求 file_facts 由 LLM 写回但 §5 缺写入口）。

- [ ] **Step 1: 写失败测试（fastmcp in-memory contract）**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_server.py -v`
Expected: FAIL（ModuleNotFoundError: threedog.server）

- [ ] **Step 3: 实现 server.py**

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_server.py -v`
Expected: `1 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/server.py tests/test_server.py
git commit -m "feat: FastMCP server（13 工具 + 3 prompts，零 LLM 调用）"
git push origin main
```

---

### Task 14: CLI（cli.py + 入口）

**Files:**
- Create: `src/threedog/cli.py`、`src/threedog/__main__.py`
- Modify: `pyproject.toml`（加 `[project.scripts]`）
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_config/save_config/AppConfig/config_dir`、`walk/diff`、`Store/Database`、`symlink_ok`；`threedog.installer.setup.run`（延迟导入，Task 16 实现）
- Produces: typer `app`，命令 `init / install / serve / scan / status`；控制台入口 `threedog`

- [ ] **Step 1: 写失败测试**

```python
from typer.testing import CliRunner

from threedog.cli import app

runner = CliRunner()


def test_init_scan_status(tmp_path, monkeypatch):
    monkeypatch.setenv("THREEDOG_HOME", str(tmp_path / "home"))
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("a")

    r = runner.invoke(app, ["init", "--db-path", str(tmp_path / "home/db.sqlite3"),
                            "--output-dir", str(tmp_path / "home/out"),
                            "--strategy", "copy"])
    assert r.exit_code == 0

    r2 = runner.invoke(app, ["scan", str(src)])
    assert r2.exit_code == 0 and "新增 1" in r2.output

    r3 = runner.invoke(app, ["status"])
    assert r3.exit_code == 0 and "'files': 1" in r3.output
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL（ModuleNotFoundError: threedog.cli）

- [ ] **Step 3: 实现**

`pyproject.toml` 在 `[project]` 段之后追加：

```toml
[project.scripts]
threedog = "threedog.cli:app"
```

`src/threedog/cli.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from threedog.config import AppConfig, config_dir, load_config, save_config

app = typer.Typer(help="threedog - 风格驱动的本地文件整理 MCP server")


@app.command()
def init(
    db_path: Optional[str] = typer.Option(None, help="数据库路径"),
    output_dir: Optional[str] = typer.Option(None, help="归类输出目录"),
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
    d = diff(store, walk(Path(directory).expanduser()))
    typer.echo(f"新增 {len(d.new)} 变更 {len(d.changed)} 删除 {len(d.deleted)}")


@app.command()
def status():
    """数据库/风格/最近批次概览。"""
    from threedog.db import Database
    from threedog.graph.store import Store

    cfg = load_config()
    store = Store(Database(cfg.db_path))
    typer.echo(store.overview())
```

`src/threedog/__main__.py`:

```python
from threedog.cli import app

app()
```

- [ ] **Step 4: 同步并验证**

Run: `uv sync`
Expected: 成功（重新生成入口脚本）

Run: `uv run pytest tests/test_cli.py -v`
Expected: `1 passed`

Run: `uv run threedog --help`
Expected: 显示 init/install/serve/scan/status 命令列表

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/cli.py src/threedog/__main__.py pyproject.toml uv.lock tests/test_cli.py
git commit -m "feat: CLI 入口（init/install/serve/scan/status）"
git push origin main
```

---

### Task 15: Skills 内容（src/threedog/skills/）

**Files:**
- Create: `src/threedog/skills/classify-files/SKILL.md`、`src/threedog/skills/find-files/SKILL.md`、`src/threedog/skills/setup-style/SKILL.md`、`src/threedog/skills/rebuild-index/SKILL.md`
- Test: `tests/test_skills.py`

**Interfaces:**
- Produces: 4 个随包分发的 SKILL.md（frontmatter 含 name/description；installer 复制时目录加 `threedog-` 前缀）

- [ ] **Step 1: 写失败测试**

```python
from pathlib import Path

SKILLS = Path(__file__).parent.parent / "src" / "threedog" / "skills"


def test_four_skills_exist_with_frontmatter():
    names = {"classify-files", "find-files", "setup-style", "rebuild-index"}
    for name in names:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        assert text.startswith("---")
        assert f"name: {name}" in text
        assert "description:" in text
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_skills.py -v`
Expected: FAIL（FileNotFoundError）

- [ ] **Step 3: 写 4 个 SKILL.md**

`src/threedog/skills/classify-files/SKILL.md`:

```markdown
---
name: classify-files
description: 用 threedog 扫描并按风格档案分类整理本地文件（organize local files by style profile）
---

# 分类整理文件

1. 调用 `scan` 获取目录的新增/变更文件清单
2. 调用 `taxonomy` 查看当前风格目录树；`get_file_cards` 批量获取文件卡片
3. 为每个文件决定分类路径 `"顶层/子类"`：顶层必须来自骨架；子类可按内容新建
4. 有把握的文件打包 `propose`，把预览表（源路径 → 目标路径 + 动作类型）展示给用户
5. 用户确认后 `apply`；对 failed/skipped 条目向用户解释原因
6. 对每个有新文件的分类写 3~5 句中文导读（该类收集什么、本期新增亮点），调用
   `write_portal`；对重要文件用 `set_file_facts` 回写摘要与关键词
7. 存疑文件逐个询问用户，或先放入「待整理」
```

`src/threedog/skills/find-files/SKILL.md`:

```markdown
---
name: find-files
description: 按模糊描述查找本地文件（find local files by fuzzy description）
---

# 查找文件

1. 从用户描述提炼多组关键词（中文/英文/文件名片段），分别调用 `search`
2. 对候选调用 `get_file_cards` 查看摘要与所在分类
3. 回复：最可能的文件路径、所在分类、相关文件；若都没有，用 `graph_overview`
   说明已索引范围，建议先 scan
```

`src/threedog/skills/setup-style/SKILL.md`:

```markdown
---
name: setup-style
description: 访谈用户并创建 threedog 风格档案（interview user and create style profile）
---

# 风格访谈

逐维提问（一次只问一维，给选项）：

1. **结构**：domain（按领域，追问领域清单）/ project（按项目）/ time（追问
   year|quarter|month）/ gtd（收件箱-下一步-资料-归档）
2. **命名**：zh / bilingual（追问英文映射）/ emoji（追问映射，未映射用 📁）/
   numbered（追问宽度）
3. **呈现**：minimal / dashboard / timeline；是否要统计、是否要导读

默认领域建议（旧项目沿用）：常规任务、职业发展、应急事务、家庭管理、个人事务、
社交关系、休闲养生。

收集完 `create_style` → `suggest_layout` 展示目录树预览 → 用户满意后
`set_active_style`。
```

`src/threedog/skills/rebuild-index/SKILL.md`:

```markdown
---
name: rebuild-index
description: 全量重建 threedog 索引与目录构造（rebuild threedog index and layout）
---

# 重建索引

1. 对各已索引根目录调用 `scan` 同步文件增删改
2. `graph_overview` 查看未归类文件数量
3. 重新 `set_active_style`（当前风格 id）重建骨架（导读自动保留）
4. 若切换了风格：先对旧批次逐个 `rollback`，再按新风格对未归类文件重新走
   classify-files 流程
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_skills.py -v`
Expected: `1 passed`

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/skills tests/test_skills.py
git commit -m "feat: 4 个随包分发的 skills（分类/查找/风格访谈/重建）"
git push origin main
```

---

### Task 16: 安装器（installer/）

**Files:**
- Create: `src/threedog/installer/__init__.py`（空）、`src/threedog/installer/detect.py`、`src/threedog/installer/setup.py`
- Test: `tests/test_installer.py`

**Interfaces:**
- Consumes: `src/threedog/skills/`（Task 15）
- Produces:
  - `detect() -> list[str]`（claude-code / claude-desktop / generic）
  - `deploy_skills(target: Path | None = None) -> list[Path]`（复制为 `~/.claude/skills/threedog-<name>/`，含 VERSION，幂等覆盖）
  - `install_claude_code() -> bool`（`claude mcp add --user threedog -- uvx threedog serve`）
  - `install_claude_desktop() -> bool`（改写 claude_desktop_config.json 的 mcpServers）
  - `install_generic(cwd=None) -> Path`（写 `.mcp.json`）
  - `run(clients=None) -> dict`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_installer.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`src/threedog/installer/detect.py`:

```python
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def claude_desktop_config() -> Path | None:
    if sys.platform == "win32":
        p = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        p = (Path.home() / "Library" / "Application Support"
             / "Claude" / "claude_desktop_config.json")
    else:
        return None
    return p if p.parent.exists() else None


def detect() -> list[str]:
    found: list[str] = []
    if shutil.which("claude"):
        found.append("claude-code")
    if claude_desktop_config() is not None:
        found.append("claude-desktop")
    found.append("generic")  # .mcp.json 始终可用
    return found
```

`src/threedog/installer/setup.py`:

```python
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from threedog import __version__
from threedog.installer.detect import claude_desktop_config

SERVER = {"command": "uvx", "args": ["threedog", "serve"]}


def _skills_source() -> Path:
    return Path(__file__).parent.parent / "skills"


def deploy_skills(target: Path | None = None) -> list[Path]:
    base = target or Path.home() / ".claude" / "skills"
    base.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for src in sorted(_skills_source().iterdir()):
        if not src.is_dir():
            continue
        dst = base / f"threedog-{src.name}"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        (dst / "VERSION").write_text(__version__, encoding="utf-8")
        out.append(dst)
    return out


def install_claude_code() -> bool:
    if not shutil.which("claude"):
        return False
    subprocess.run(
        ["claude", "mcp", "add", "--user", "threedog", "--",
         "uvx", "threedog", "serve"],
        check=False)
    return True


def install_claude_desktop() -> bool:
    cfg = claude_desktop_config()
    if cfg is None:
        return False
    data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
    data.setdefault("mcpServers", {})["threedog"] = SERVER
    cfg.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def install_generic(cwd: Path | None = None) -> Path:
    p = (cwd or Path.cwd()) / ".mcp.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    data.setdefault("mcpServers", {})["threedog"] = SERVER
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def run(clients: list[str] | None = None) -> dict:
    from threedog.installer.detect import detect
    chosen = clients or detect()
    result: dict = {}
    if "claude-code" in chosen:
        result["claude-code"] = install_claude_code()
    if "claude-desktop" in chosen:
        result["claude-desktop"] = install_claude_desktop()
    if "generic" in chosen:
        result["generic"] = str(install_generic())
    result["skills"] = [str(p) for p in deploy_skills()]
    return result
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run pytest tests/test_installer.py -v`
Expected: `4 passed`

Run: `uv run threedog install`
Expected: 输出包含 `skills` 部署清单（本机检测到什么客户端就装什么）

- [ ] **Step 5: 提交并推送**

```bash
git add src/threedog/installer tests/test_installer.py
git commit -m "feat: 安装器（客户端检测/MCP 配置写入/skills 部署）"
git push origin main
```

---

### Task 17: 旧代码清理、双语 README、CI/发布流水线

**Files:**
- Delete: `miaomiao/`、`main.py`、`example/`
- Move: `doc/plantuml` → `docs/legacy/plantuml`、`doc/FAQ` → `docs/legacy/FAQ`
- Create: `README.md`（重写）、`README.zh-CN.md`、`.github/workflows/ci.yml`、`.github/workflows/publish.yml`
- Modify: `pyproject.toml`（ruff extend-exclude 收窄为 `["tmp"]`）
- Test: 全量 `uv run pytest` + `uv run ruff check .`

**Interfaces:**
- Consumes: 全部前序任务
- Produces: 可发布的开源仓库形态

- [ ] **Step 1: 删除旧代码并迁移文档**

```bash
git rm -r -q miaomiao example main.py
mkdir -p docs/legacy
git mv doc/plantuml docs/legacy/plantuml
git mv doc/FAQ docs/legacy/FAQ
rmdir doc 2>/dev/null || true
```

`pyproject.toml` 中 `extend-exclude = ["miaomiao", "example", "tmp", "doc"]` 改为：

```toml
extend-exclude = ["tmp"]
```

- [ ] **Step 2: 写双语 README**

`README.md`（英文，重写）:

```markdown
# threedog

Style-driven local file organizer, delivered as an [MCP](https://modelcontextprotocol.io) server + skills.

## Why

Computers accumulate files faster than we organize them. threedog indexes your
files, classifies them with your AI assistant, and rebuilds a style-personalized
directory layout — with portal pages (`INDEX.md`) per category.

## Features

- **Style profiles** — structure (domain/project/time/GTD) × naming
  (zh/bilingual/emoji/numbered) × portal (minimal/dashboard/timeline)
- **Safe by design** — every mutation goes through preview → apply; journal-based
  rollback per batch; link/move/copy strategies
- **Local-first** — single SQLite database with FTS5 full-text search; no cloud,
  no LLM calls inside the server
- **Open protocol** — works with Claude Code, Claude Desktop, and any MCP client

## Install

    uvx threedog init      # config wizard (db path, output dir, strategy)
    uvx threedog install   # register MCP server + deploy skills

Then ask your assistant: *"organize my Downloads"* — the `classify-files` skill
takes over.

## CLI

    threedog scan <dir>    # index a directory
    threedog status        # db / style / recent batches

## Development

    uv sync
    uv run pytest
    uv run ruff check .

## License

Apache-2.0
```

`README.zh-CN.md`:

```markdown
# threedog

风格驱动的本地文件整理工具，以 [MCP](https://modelcontextprotocol.io) server + skills 形态交付。

## 解决什么问题

电脑里文件积累的速度远超整理的速度。threedog 索引本地文件，由 AI 助手按你的
风格档案分类，生成个性化的目录构造，每个分类附带门户页（`INDEX.md`）。

## 特性

- **风格档案**：结构（领域/项目/时间/GTD）× 命名（中文/双语/emoji/编号）×
  呈现（极简/仪表盘/时间线）
- **安全设计**：所有写操作走 预览 → 执行 流水线；按批次账本回滚；
  软链/移动/复制三种策略
- **本地优先**：单文件 SQLite + FTS5 全文检索；server 内零 LLM 调用
- **开放协议**：Claude Code / Claude Desktop / 任意 MCP 客户端可用

## 安装

    uvx threedog init      # 配置向导（数据库、输出目录、默认策略）
    uvx threedog install   # 注册 MCP server + 部署 skills

然后对助手说「整理一下我的下载目录」，`classify-files` skill 会接管流程。

## 开发

    uv sync
    uv run pytest
    uv run ruff check .

## 许可

Apache-2.0
```

- [ ] **Step 3: 写 CI 与发布流水线**

`.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run pytest -q
```

`.github/workflows/publish.yml`:

```yaml
name: Publish
on:
  push:
    tags: ["v*"]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

- [ ] **Step 4: 全量验证**

Run: `uv run pytest -q`
Expected: 全部通过（此前累计 30+ 项）

Run: `uv run ruff check .`
Expected: `All checks passed!`

Run: `uv build`
Expected: dist/ 下生成 wheel，`unzip -l` 确认含 `threedog/skills/*/SKILL.md`

- [ ] **Step 5: 提交并推送**

```bash
git add -A
git commit -m "chore: 移除旧 miaomiao 代码，双语 README，CI 与 PyPI 发布流水线"
git push origin main
```

---

## 完成定义

- `uv run pytest` 全绿、`uv run ruff check .` 无告警、`uv build` 产物含 skills
- 17 个任务各一次 commit + push（多提交多推送），`origin/main` 与本地一致
- `uvx threedog init && uvx threedog install` 在干净环境可跑通

