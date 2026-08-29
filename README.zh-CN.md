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
