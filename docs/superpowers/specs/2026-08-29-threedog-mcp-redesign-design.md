# threedog MCP 重设计（v1）

- 日期：2026-08-29
- 状态：已与用户逐节确认
- 参考：[tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph)（Python + FastMCP + skills 模式，31k star 验证）

## 1. 背景与目标

threedog（原 miaomiao/computertool）当前是一个自建 agent 循环的本地文件分类工具：pyautogen 驱动 LLM 分类，结果写入 Neo4j，软链归类。重设计目标：

- 从"自建 agent"转为 **MCP server（能力层）+ skills（编排层）**，推理交给 host（Claude 等 MCP 客户端）
- 去外部服务依赖：**砍掉 Neo4j，SQLite local-first**
- 差异化卖点：**风格档案**——询问用户风格，按风格生成不同的目录构造与门户呈现
- 按开源项目标准交付：PyPI + uvx + `threedog install` + 双语文档 + CI

### 非目标（v1 明确不做）

- HTML 门户渲染（v2，渲染器已留接口）
- 后台 daemon 文件监听增量更新（按需扫描即可满足 v1）
- 交互性格风格（原澄清中的 D 维度，用户明确排除）
- 旧 Neo4j 数据迁移（首次全量扫描重建）

## 2. 已确认的核心决策

| 决策点 | 结论 |
|---|---|
| 形态 | Python MCP server（FastMCP）+ skills，参考 code-review-graph 分工 |
| 存储 | 单文件 SQLite + FTS5，数据库默认 `~/.threedog/threedog.db` |
| 分工 | skill = 编排方法论；MCP server = 能力与写操作（mutations）；server 内零 LLM 调用 |
| 风格档案维度 | A 组织结构 + B 命名约定 + C 呈现形式 |
| 风格引擎 | 骨架确定性（模板渲染）+ 叙述 LLM 化（Claude 写导读，经工具落盘） |
| 写操作策略 | link/move/copy 策略模式，默认 link，共用 preview → apply 流水线 |
| 呈现载体 | Markdown 先行（jinja2 三套版式），HTML 留接口 |
| 分发 | 开源标准：PyPI、uvx、install 命令、中英文档、GitHub Actions |

## 3. 总体架构

```
threedog/                        # 现仓库就地重构（git 历史保留）
├── src/threedog/
│   ├── cli.py                   # typer 入口: init / install / serve / scan / status
│   ├── server.py                # FastMCP server 装配
│   ├── config.py                # config.toml + style profile 加载
│   ├── db.py                    # SQLite 连接 + schema 版本迁移
│   ├── graph/
│   │   ├── store.py             # files/categories/assignments CRUD + FTS5
│   │   └── schema.sql
│   ├── scan/
│   │   ├── walker.py            # 目录遍历 + 元数据提取
│   │   └── incremental.py       # 快照对比：新增/变更/删除
│   ├── style/
│   │   ├── profile.py           # StyleProfile pydantic 模型
│   │   ├── skeleton.py          # 结构骨架生成（确定性）
│   │   ├── naming.py            # 命名规则应用（确定性）
│   │   └── renderers/           # jinja2 门户渲染：minimal/dashboard/timeline
│   ├── actions/
│   │   ├── pipeline.py          # preview → apply 统一流水线
│   │   ├── strategies.py        # link/move/copy 策略
│   │   └── journal.py           # 操作日志（rollback 依据）
│   └── installer/
│       ├── detect.py            # 检测已安装 AI 客户端
│       └── setup.py             # 写 MCP 配置 + 部署 skills + 注入规则
├── skills/                      # 随包分发的 4 个 skill 源
├── tests/
├── .github/workflows/ci.yml
├── pyproject.toml               # hatchling；deps: fastmcp, pydantic, jinja2, typer
├── README.md / README.zh-CN.md
└── docs/
```

依赖：`fastmcp>=3.2.4,<4`、`pydantic`、`jinja2`、`typer`。
删除依赖：pyautogen、py2neo（连带 `miaomiao/`、`main.py`、`example/`）。

## 4. 数据模型（SQLite + FTS5）

```sql
files          (id, path UNIQUE, name, ext, size, mtime,
                first_seen, last_seen, deleted)          -- 扫描层事实
file_facts     (file_id, summary, keywords, extracted_at) -- LLM 摘要写回
categories     (id, parent_id, name_raw, name_display,
                path, style_id, sort)                     -- 骨架实例化后的树
assignments    (id, file_id, category_id, strategy,
                status, created_at)                       -- 归类关系（apply 产物）
style_profiles (id, name, structure_type,
                naming JSON, presentation JSON, active)   -- 风格档案
journal        (id, ts, batch_id, action JSON,
                status, rollback_info)                    -- 写操作日志
-- FTS5 虚表: file_search(name, summary, keywords)
```

设计要点：

- 图形态是**树 + 少量多对多关联**，关系表足以表达，不引入 networkx
- categories 只存逻辑名 `name_raw`；显示名 `name_display` 由命名规则渲染，换命名风格不改数据
- journal 按 batch_id 分组，rollback 以批次为单位反序执行

## 5. MCP 工具（读写分离，server 零 LLM）

### 读

| 工具 | 作用 |
|---|---|
| `scan(dir, incremental=true)` | 遍历 → 登记 files 表 → 返回 新增/变更/删除 清单 |
| `get_file_cards(paths)` | 批量文件卡片：元数据 + 摘要 + 已有归类（Claude 分类依据） |
| `search(query)` | FTS5 全文 + 文件名/路径/关键词匹配 |
| `graph_overview()` | 文件数、分类树、最近变化、待归类堆积 |
| `taxonomy(style_id?)` | 当前风格完整目录树骨架 |
| `suggest_layout(style_id)` | dry-run：渲染"按此风格的目录树"，不落盘 |

### 写（全部经 preview → apply 流水线）

| 工具 | 作用 |
|---|---|
| `create_style(profile)` / `set_active_style(id)` | 风格档案管理 |
| `propose(pairs)` | `[(file, category)]` → 生成 plan（batch_id + 预览表 + 冲突标记），不动文件 |
| `apply(batch_id)` | 执行：建目录骨架 + link/move/copy + journal + INDEX.md 骨架 |
| `write_portal(category, markdown)` | 叙述层内容写入 INDEX.md 叙述插槽 |
| `rollback(batch_id)` | 按 journal 反序：删链/移回原路径/删副本；assignments 置 revoked |

### MCP prompts

`classify_files`、`find_files`、`style_interview`

## 6. Skills（编排层，随包分发）

| Skill | 编排流程 |
|---|---|
| `classify-files` | scan → get_file_cards → Claude 按风格档案判断 → propose → 展示预览表 → 用户确认 → apply → Claude 写分类导读 → write_portal → 汇总报告（有把握的直接提案，存疑的逐个问） |
| `find-files` | 理解模糊描述 → search + graph_overview → 路径 + 所在分类 + 相关文件 |
| `setup-style` | 风格访谈（结构/命名/呈现逐维提问）→ create_style → suggest_layout 预览 → set_active_style |
| `rebuild-index` | 全量重扫 + 按 active style 重建目录树与门户；切换风格 = 回滚旧批次 → 按新风格重建 |

## 7. 风格档案

```toml
[profile]
name = "我的工作台"
structure = "domain"          # domain | project | time | gtd

[structure.options]           # 参数随结构类型变化：
                               #   domain → domains 领域清单；project → projects 项目清单
                               #   time → granularity(year|quarter|month)；gtd → 无额外参数
domains = ["职业发展", "生活", "家庭", "学习"]
depth = 2                     # 骨架预生成层级
inbox = true                  # 含"待整理"收件箱

[naming]
convention = "emoji"          # zh | bilingual | emoji | numbered
emoji_map = { 职业发展 = "💼", 生活 = "🌿", 家庭 = "🏠", 学习 = "📚" }
number_width = 2              # numbered: 01-职业发展

[presentation]
portal = "dashboard"          # minimal | dashboard | timeline
show_stats = true
narration = true              # INDEX.md 留叙述插槽
```

- 多套 profile 共存，仅一个 active
- 结构类型：`domain`（领域清单 × depth）、`time`（按 mtime 自动生成 年/季/月）、`gtd`（收件箱/下一步/资料/归档）、`project`（项目清单由 profile 声明）
- 初始 `domains` 默认值沿用旧 `config.toml` 的 `top_field`

## 8. 风格引擎（两层分离）

### 结构层（确定性、纯代码、可单测）

- `skeleton.py`：structure + options → 目录树骨架 → categories 表
- `naming.py`：name_raw → name_display；做 Windows 保留名过滤与 NFC 规范化
- `renderers/`：jinja2 渲染 INDEX.md（minimal/dashboard/timeline 三套），含 `<!-- narration -->` 插槽；`Renderer` 抽象基类为 v2 HTMLRenderer 留接口

### 叙述层（LLM、skill 编排）

- apply 生成骨架门户后，skill 引导 Claude 读该分类文件卡片 → 写 3~5 句导读 + 本期新增 → `write_portal` 写入插槽
- 叙述内容存库，模板重渲染不丢失

## 9. 写操作流水线

```
propose(pairs)
  → plan(batch_id)：每条含 src、dst、strategy、冲突检测（目标同名→标红）
  → 返回预览表（纯数据，不动文件）
       ↓  用户在会话中确认（skill 层负责）
apply(batch_id)
  → 逐条执行 link/move/copy；单条失败不中断批次
  → 写 journal + assignments + 生成 INDEX.md 骨架
       ↓
rollback(batch_id)
  → 按 journal 反序执行；assignments 置 revoked
  → 删除该批次生成的 INDEX.md，清理因此变空的目录
```

安全细节：

- preview 存库，24 小时过期；apply 前逐条校验源文件存在且 mtime 未变，否则该条标 stale 拒绝
- Windows 软链权限（开发者模式/管理员）在 init/install 自检 + preview 阶段提示，不在 apply 中途失败；不可用建议切 copy
- move/copy 先落盘 rollback_info（原路径）再执行
- 路径超长用 `\\?\` 前缀处理

## 10. CLI 与分发

```
uvx threedog init        # 配置向导：数据库位置、输出目录、默认策略、软链权限自检
uvx threedog install     # 检测客户端 → 写 MCP 配置 + 部署 skills + 注入规则；幂等
uvx threedog serve       # 启动 MCP server（正常由客户端拉起）
uvx threedog scan <dir>  # CLI 直接扫描
uvx threedog status      # 数据库/风格/最近批次概览
```

- v1 支持客户端：Claude Code（`claude mcp add`）、Claude Desktop（写 `claude_desktop_config.json`）、通用 `.mcp.json`
- skills 部署到 `~/.claude/skills/`，版本号嵌入，重装覆盖
- CI：ruff + pytest（Windows + Ubuntu 矩阵，软链测试 Windows 条件跳过）+ build；tag 触发 PyPI 发布

## 11. 错误处理

| 场景 | 处理 |
|---|---|
| 软链无权限 | init/install 自检警告；preview 提示切 copy |
| 批次单条失败 | 不中断，汇总 成功/失败/跳过 |
| preview 后源文件变动 | 该条 stale 拒绝，需重新 propose |
| 数据库损坏 | schema 版本化迁移；损坏提示重建（仅索引损失，文件无损） |
| Windows 260 路径限制 | `\\?\` 前缀 + 非法字符清洗 |

## 12. 测试策略

- 确定性层（skeleton/naming/renderers/pipeline/rollback）单测全覆盖
- FTS5 中文检索专项（unicode61 按字切分行为验证）
- MCP contract 测试：fastmcp in-memory Client 逐工具断言 schema
- 端到端：tmp 文件树 → scan → propose → apply → 断言结构/INDEX.md/journal → rollback → 断言还原

## 13. 旧代码迁移

- 删除：`miaomiao/` 整包、`main.py`、`example/`
- 保留资产：`config.toml` 的 `top_field` → 新配置 domain 默认值；`doc/plantuml/` → `docs/legacy/`
- Neo4j 数据不迁移，首次 `scan` 全量重建
- 本地个人目录（`职业发展/` 等）保持 gitignore
