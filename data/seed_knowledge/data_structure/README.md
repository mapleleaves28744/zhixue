# 数据结构 GraphRAG-ready 课程知识库

> 文档状态：Phase 1 种子知识库工程目录

本目录用于构建《数据结构》课程的 GraphRAG-ready v0 知识库。Phase 1 的目标不是完整 Microsoft GraphRAG，而是先形成可追溯、可重复、可评估的课程资料底座。

## 构建原则

1. 所有外部资料必须先进入 `sources_manifest.yml`。
2. 只有 `import_status=approved_importable` 且 `review_status=approved` 的资料允许下载并进入 `raw/`。
3. `approved_link_only` 资料只保留链接、章节映射和引用说明，不复制全文。
4. `data/数据结构知识库` 只作为自有 AI 整理草稿，导入后标记为 `self_curated_draft`。
5. 每个 normalized 文档必须带 source、license、chapter、attribution 等 frontmatter。

## 目录说明

- `raw/`：经审核允许导入的原始资料。
- `normalized/`：结构化清洗后的 Markdown 语料。
- `graph/`：GraphRAG-ready v0 实体、关系、声明和先修边。
- `wiki_seed/`：可导入 LLM Wiki 的初始页面草稿。
- `eval/`：标准问题、质量报告和评估结果。
- `artifacts/`：从自有草稿迁移的题库、代码示例和图谱辅助文件。

## 推荐执行顺序

```powershell
python scripts/discover_course_sources.py
python scripts/ingest_course_materials.py --download-approved
python scripts/evaluate_course_kb.py --source-root data/seed_knowledge/data_structure
python scripts/build_data_structure_kb.py --dry-run --use-mock-embedding
```

## 专业知识库流水线

Phase 1 必须显式跟踪下面这条流水线，不只停留在“资料包 + 向量库”：

```text
原始文档
  ↓
文档解析：PDF / Word / Excel / Markdown / 网页
  ↓
清洗：去重、去噪、格式统一
  ↓
切片：按标题、段落、表格、语义切分
  ↓
Embedding：文本转向量
  ↓
索引：向量索引 + 关键词索引 + 元数据索引
  ↓
检索：向量检索 / 关键词检索 / 混合检索
  ↓
Rerank：重新排序最相关片段
  ↓
LLM 回答：基于资料生成答案
  ↓
引用来源：返回文档名、页码、段落
  ↓
反馈优化：记录错答、漏召回、低质量回答
```

`evaluate_course_kb.py` 会把以上阶段写入 `eval/quality_report.json` 的 `pipeline_stages`。其中 Embedding、索引、检索、回答和引用依赖 `build_data_structure_kb.py` 入库后的后端链路；Rerank 与知识库专用反馈闭环在 Phase 1 中只标记状态，不冒充已完成。

## 切片与 Embedding 决策

Phase 1 后续真实入库必须使用下面的切片策略：

```text
标题层级 + 语义块 + token-aware + overlap + metadata
```

切片不得退化为简单字符硬切。建议参数：

- 普通知识解释：`500-700 tokens`，overlap `80-120 tokens`。
- 定义、复杂度结论、易错点：优先整体保留。
- Python 代码块：优先整体保留，不切断类、函数、缩进块。
- 表格/公式：优先整体保留，无法解析时保留 Markdown 原文或占位符。

每个 chunk 必须写入：

```text
source_id
chapter_id
license
source_url
heading_path
chunk_type
text_hash
chunk_index
```

真实 Embedding 默认使用：

```text
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1024
```

当前数据库向量字段是 `Vector(1024)`，因此真实 OpenAI-compatible embedding 请求必须显式传 `dimensions=1024`。禁止在没有 migration 的情况下使用 `text-embedding-3-small` 默认维度或改成 `text-embedding-3-large` 默认维度直接入库。

真实入库必须额外提供课程和用户：

```powershell
python scripts/build_data_structure_kb.py --course-id <course_id> --user-id <owner_user_id> --use-mock-embedding
```
