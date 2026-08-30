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
