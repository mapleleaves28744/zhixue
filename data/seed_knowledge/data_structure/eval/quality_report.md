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
- Embedding：ready_for_build；build_data_structure_kb.py 调用 EmbeddingService；--use-mock-embedding 可无 Key 演示。
- 索引：partial；当前 DB 支持向量检索与 extra_meta 元数据；关键词检索仍是文本兜底，未建正式关键词索引。
- 检索：ready_for_query_after_build；POST /api/v1/knowledge/search 使用 VectorRetriever，并带文本兜底与课程/用户可见性校验。
- Rerank：planned；Phase 1 暂无独立 reranker；当前按向量距离或文本分数排序。
- LLM 回答：ready_for_query_after_build；Tutor/Wiki/Resource Agent 通过 LLM Provider 消费检索片段；Mock Provider 保证可演示。
- 引用来源：ready_for_query_after_build；Tutor/Resource 输出 citations；WikiSource 记录 source_type/source_id/quote_text。
- 反馈优化：partial；已有 Tutor/推荐反馈表；知识库专用漏召回/错答评估闭环尚未完成。

> Phase 1 仅建设 GraphRAG-ready v0，不执行完整 Microsoft GraphRAG community summaries。
