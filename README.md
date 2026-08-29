# threedog

一个结合知识图谱与大模型的本地文件智能管理工具。

## 介绍

电脑在长期使用中会积累大量生活、工作相关的文件，内容多且杂，普通人很难持续做好分类汇总；加上记忆的模糊性，一段时间后往往只剩模糊印象，难以快速找到需要的数据。

threedog 通过大模型对本地文件进行分析与自动分类，并将结果录入知识图谱，使本地数据更规范有序、便于查阅：

- 扫描指定工作目录，提取文件属性与内容特征
- 结合大模型（OpenAI 兼容接口）进行多步分析与自动分类
- 结果写入 Neo4j 图数据库，构建可检索的知识图谱
- 支持按「常规任务 / 职业发展 / 应急事务 / 家庭管理 …」等顶层领域归类

## 环境要求

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/)
- Neo4j 图数据库

## 快速开始

```bash
uv sync

# 创建本地配置（config.toml 包含 API Key，已被 gitignore，请勿提交）
cp miaomiao/config.example.toml miaomiao/config.toml
# 编辑 config.toml，填入 api_key、base_url、model 以及 analysis_dir / output_dir

uv run main.py
```

## 配置说明

| 配置项 | 说明 |
|---|---|
| `analysis_dir` | 待分析的本地目录列表 |
| `output_dir` | 分类结果输出目录 |
| `top_field` | 顶层分类领域 |
| `ai.api_key` | OpenAI 兼容接口的 API Key |
| `ai.base_url` | 模型服务地址 |
| `ai.model` | 模型名称 |

## 目录结构

```
main.py               # 入口：遍历目录并调度分析
miaomiao/
  action.py           # 大模型分析动作
  control.py          # 控制器
  config/             # 配置加载
  data/               # 文件与数据库模型
  model/              # 模型客户端
  prompt/             # 提示词模板
doc/                  # 设计文档（PlantUML）与 FAQ
example/              # 示例代码
```

## License

[LICENSE](LICENSE)
