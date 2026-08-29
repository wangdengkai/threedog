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
