---
name: find-files
description: 按模糊描述查找本地文件（find local files by fuzzy description）
---

# 查找文件

1. 从用户描述提炼多组关键词（中文/英文/文件名片段），分别调用 `search`
2. 对候选调用 `get_file_cards` 查看摘要与所在分类
3. 回复：最可能的文件路径、所在分类、相关文件；若都没有，用 `graph_overview`
   说明已索引范围，建议先 scan
