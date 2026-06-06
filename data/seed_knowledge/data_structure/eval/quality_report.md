# 数据结构 GraphRAG-ready 知识库质量报告

## 总览

- 原始文档：21
- 资料源数量：6
- 已审核资料源：6
- 可导入资料源：5
- 章节覆盖：19 / 19 (100%)
- normalized 文档：32
- 来源可追溯率：100%
- 标准问题数：30
- 公有课程：DS-PUBLIC / public_template
- 实际入库：32 份资料 / 1608 chunks / 1608 embeddings / 125 知识点
- Embedding：sentence_transformers / BAAI/bge-large-zh-v1.5 / 1024 维 / allow_mock_fallback=False
- 标准问题检索召回率：97%
- 标准问题回答准确率：97%
- 标准问题幻觉率：3%
- 标准问题引用率：100%

## GraphRAG-ready v0

- 实体数：10
- 关系数：8
- 声明数：6
- 状态：ready

## 知识库流水线

- 原始文档：ready；raw 文件 21 份；normalized 文档 32 份。
- 文档解析：ready；ingest_course_materials.py 已支持 HTML/Markdown/RST/PDF 到 normalized Markdown。
- 清洗与格式统一：ready；normalized docs: 32; source traceability: 100%
- 层级切片：ready；backend/app/rag/chunking.py 保留 heading_path，并保护代码块。
- Embedding：ready；1608/1608 chunks 已使用 sentence_transformers / BAAI/bge-large-zh-v1.5 / 1024 维真实向量化；allow_mock_fallback=False。
- 索引：ready；pgvector HNSW、内容 pg_trgm 关键词索引和 extra_meta GIN 元数据索引均已建立。
- 检索：ready；HybridRetriever 已完成向量、关键词、metadata 混合检索；30 个标准问题检索召回率 97%。
- Rerank：ready；HybridRetriever 已执行向量分数、关键词分数、metadata 与来源多样性的轻量规则 rerank。
- LLM 回答：ready；已通过真实 LLM 完成 3 个 RAG 样例回答，fallback_used=false。
- 引用来源：ready；标准问题评测引用率 100%；Tutor 输出可追溯 citations。
- 反馈优化：ready；已生成标准问题逐题命中记录；回答准确率 97%，幻觉率 3%。

> Phase 1 仅建设 GraphRAG-ready v0，不执行完整 Microsoft GraphRAG community summaries。
