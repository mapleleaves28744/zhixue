# 15_RAG与知识库设计

## 目录导读

> 文档状态：**当前实现与增强边界**
>
> 当前实现事实优先参考：`docs/当前实现基线.md`、当前代码、OpenAPI、SQLAlchemy Model 与验收记录。

本文合并了本目录原有占位主题。阅读顺序：

- [当前流水线](#当前流水线)
- [切片与Embedding](#切片与embedding)
- [检索与引用](#检索与引用)
- [评估和后续增强](#评估和后续增强)

## 当前流水线

资料经上传、文本解析、文档切片、Embedding、知识点抽取后进入课程知识库。当前核心实现位于 `material_parse_service.py`、`chunk_service.py`、`embedding_service.py`、`knowledge_service.py`、`rag/chunking.py` 和 `rag/retriever.py`。

## 切片与Embedding

- 切片保留资料、课程和顺序信息，服务于来源追溯。
- Embedding 维度必须与数据库向量字段一致。
- 检索必须带 `course_id` 和当前用户权限上下文。
- 无真实 Embedding 时允许 Mock，确保链路可演示。

## 检索与引用

当前以 pgvector 课程内向量检索为主，检索结果用于 Wiki、Tutor 和资源生成。回答引用应返回资料或 Wiki 来源，使前端能展示“依据是什么”。当前未实现完整混合检索、Rerank 和 GraphRAG，不得在演示中夸大。

## 评估和后续增强

现阶段评估重点是检索结果归属正确、课程隔离、引用可追溯和主链路稳定。后续可增加召回率测试、固定问题集、关键词+向量混合检索、Rerank 和图谱辅助检索。
