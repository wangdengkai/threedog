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
