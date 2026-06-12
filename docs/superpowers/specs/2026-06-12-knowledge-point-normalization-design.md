# 细粒度知识点归一化与 Wiki 整理设计

> 文档状态：新增能力设计规格  
> 日期：2026-06-12  
> 目标：将每份课程资料整理为 15-30 个有来源、可分组、可生成 Wiki 的细粒度知识点，避免规则抽取噪声直接变成 Wiki 页面。

## 1. 当前问题

当前资料入库链路为：

```text
文档切片
  → KnowledgeService 正则抽取标题、定义句和编号项
  → 按名称完全匹配去重并写入 knowledge_points
  → WikiGenerateService 读取课程所属用户的全部知识点
  → 为每个知识点生成 Wiki
```

这会产生四类问题：

1. Markdown 标记、半句话、教学说明和编号项可能被识别为知识点。
2. “链栈”“链式栈”“栈的链式存储”等同义概念无法合并。
3. 缺少章节、父子层级和可靠排序，Wiki 页面只能平铺展示。
4. Wiki 生成读取课程全部知识点，可能把其他资料的知识点混入当前资料生成结果。

## 2. 目标与非目标

### 2.1 目标

1. 每份资料默认保留 15-30 个细粒度知识点。
2. 使用“规则召回候选 + LLM 归一化整理 + 确定性校验”的混合流程。
3. 真实 LLM 不可用时，使用增强规则整理，保证 Mock 演示链路可运行。
4. 为每个知识点记录来源 chunk、别名、置信度、整理方式和拒绝原因摘要。
5. Wiki 只为当前资料整理并绑定的知识点生成页面。
6. `/knowledge` 显示候选、合并、拒绝、保留和 Wiki 生成数量。
7. 不删除已有知识点、Wiki 页面或历史版本。

### 2.2 非目标

1. 本次不新增独立人工审核工作台。
2. 本次不自动删除或重写历史脏知识点。
3. 本次不重做 `/knowledge` 页面布局。
4. 本次不引入新的 Agent 框架或外部知识图谱框架。

## 3. 总体流程

```text
资料 chunks
  → 规则粗抽取 40-80 个候选
  → 候选清洗与来源 chunk 绑定
  → LLM 归一化为 15-30 个知识点
  → 程序执行名称、来源、数量和层级校验
  → 写入或复用 knowledge_points
  → 回写 chunk.knowledge_id
  → 推断知识关系
  → 仅为本次资料知识点生成 Wiki
```

## 4. 归一化结果结构

归一化器返回一个不直接暴露数据库模型的结构化结果：

```json
{
  "candidate_count": 58,
  "merged_count": 17,
  "rejected_count": 14,
  "kept_count": 27,
  "used_llm": true,
  "items": [
    {
      "canonical_name": "链式栈",
      "aliases": ["链栈", "栈的链式存储"],
      "chapter": "栈与队列",
      "parent_name": "栈",
      "description": "使用链式存储结构实现的栈。",
      "importance": "normal",
      "difficulty": "medium",
      "sort_order": 12,
      "source_chunk_ids": ["chunk_uuid"],
      "confidence": 0.91,
      "decision_reason": "合并同义候选并保留资料中的定义来源"
    }
  ],
  "rejected": [
    {
      "raw_name": "**知识图谱建议关系",
      "reason": "包含 Markdown 标记且不是课程概念"
    }
  ]
}
```

## 5. 候选抽取与确定性校验

### 5.1 规则粗抽取

规则层负责高召回，不直接决定最终知识点：

1. 提取章节标题、小节标题、定义句主语和编号条目。
2. 每个候选必须携带来源 chunk ID 和资料内出现顺序。
3. 单份资料最多向归一化器提交 80 个候选。

### 5.2 名称清洗

程序在调用 LLM 前后均执行名称清洗：

1. 去除 Markdown 标记、编号前缀、首尾标点和多余空白。
2. 拒绝长度小于 2 或大于 32 的名称。
3. 拒绝仅包含数字、标点或格式符号的名称。
4. 拒绝明显完整句、操作提示和模板措辞。
5. 名称比较使用清洗后的大小写无关键。

### 5.3 最终质量门槛

最终保留项必须：

1. 有非空规范名称。
2. 至少绑定一个当前资料 chunk。
3. 通过确定性名称校验。
4. 与同批次知识点不存在规范名称重复。
5. 数量不超过 30。

若合格知识点超过 30，按来源覆盖度、置信度、重要程度和出现顺序排序后截取。若不足 15，不强行虚构知识点，保留真实合格结果并在响应中标记数量不足。

## 6. LLM 整理与降级

### 6.1 LLM 职责

LLM 仅负责：

1. 规范知识点名称。
2. 合并同义候选。
3. 分配章节和父知识点。
4. 生成简短描述、重要程度和难度。
5. 给出保留、合并或拒绝理由。

LLM 不直接写数据库，也不得创建没有来源候选支撑的新知识点。

### 6.2 调用方式

通过统一 LLM Provider 调用，优先使用 `structured_chat()` 和 Pydantic Schema。场景名使用 `knowledge.normalize`，调用记录进入现有 `llm_call_logs`。

### 6.3 Mock 与失败降级

当真实 LLM 不可用、结构化结果校验失败或调用异常时：

1. 使用清洗后的规则候选。
2. 按规范名称键合并重复项。
3. 从标题层级推断章节。
4. 按资料出现顺序排序。
5. 保留最多 30 个合格项。

降级结果必须返回 `used_llm=false` 和明确的 `fallback_reason`，不得伪装为真实模型整理。

## 7. 数据落地

首版不新增数据库表或 migration，复用现有字段：

| 数据 | 落地位置 |
|---|---|
| 规范名称 | `knowledge_points.name` |
| 章节 | `knowledge_points.chapter` |
| 父知识点 | `knowledge_points.parent_id` |
| 描述、难度、重要程度、顺序 | 对应现有字段 |
| 别名、置信度、来源 chunk IDs、整理方式 | `knowledge_points.extra_meta.normalization` |
| chunk 与知识点绑定 | `document_chunks.knowledge_id` |
| 来源引用 | 生成 Wiki 时写入 `wiki_sources` |

已有同名知识点优先复用，不覆盖用户手工内容；仅补充缺失的归一化元数据和当前资料来源。

## 8. API 兼容设计

保留现有接口：

```http
POST /api/v1/knowledge/extract-from-material
```

响应保留 `extracted_count`、`relations_created` 和 `points`，新增：

```json
{
  "normalization": {
    "candidate_count": 58,
    "merged_count": 17,
    "rejected_count": 14,
    "kept_count": 27,
    "used_llm": true,
    "fallback_reason": null
  }
}
```

`POST /api/v1/wiki/pages/generate-from-material` 不改变请求格式，但内部仅选择 `extra_meta.normalization.source_material_ids` 包含当前 `material_id` 的知识点。

## 9. Wiki 生成与展示

### 9.1 Wiki 生成范围

Wiki 生成服务仅处理当前资料绑定的归一化知识点。没有当前资料绑定知识点时返回明确业务错误，不再回退到课程全部知识点。

### 9.2 页面排序

Wiki 页面列表继续使用现有接口。前端在 `/knowledge` 中根据知识点元数据按以下顺序展示：

```text
章节
  → 父知识点
  → sort_order
  → 页面标题
```

本次仅增强现有卡片区域和流水线文案，不改变 Stitch 导航、侧栏或主布局。

### 9.3 过程反馈

资料详情和完整入库流水线显示：

```text
粗抽取 58 个候选 → 合并 17 个 → 拒绝 14 个 → 保留 27 个 → 生成 27 个 Wiki
```

若使用规则降级，应显示“已使用规则整理”，避免把 Mock 或降级结果描述为真实 LLM 效果。

## 10. 错误处理

1. 没有 chunks：沿用现有“请先执行 chunk 操作”错误。
2. 所有候选均被拒绝：返回明确业务错误，不生成占位知识点。
3. LLM 失败：自动使用规则降级，主链路继续。
4. 数据库写入失败：事务回滚，不留下部分知识点或部分 Wiki。
5. Wiki 生成缺少资料绑定知识点：返回“当前资料尚无已整理知识点”。

## 11. 测试与验收

### 11.1 后端测试

1. Markdown 标记、半句话和操作提示会被拒绝。
2. 同义或重复候选可合并为规范名称。
3. 每份资料最多保留 30 个知识点。
4. 每个保留知识点至少绑定一个当前资料 chunk。
5. LLM 失败时规则降级可运行并正确标记。
6. Wiki 生成不会混入其他资料知识点。
7. 重复执行不会破坏已有 Wiki 或创建重复知识点。

### 11.2 前端验收

1. `/knowledge` 显示整理统计。
2. 完整流水线显示“候选、合并、拒绝、保留、Wiki”步骤结果。
3. 降级时显示真实状态。
4. 原 Stitch 页面布局和导航保持不变。

### 11.3 阶段验收

执行后端专项测试、前端构建、文档检查和 `scripts/local_check.ps1 -Backend/-Frontend`。只有本地验收通过后，才可宣称知识点整理与 Wiki 联动完成。

## 12. 修改范围

预计修改：

```text
backend/app/services/knowledge_service.py
backend/app/services/knowledge_normalization_service.py
backend/app/services/wiki_generate_service.py
backend/app/repositories/knowledge_repository.py
backend/app/repositories/chunk_repository.py
backend/app/schemas/knowledge.py
backend/app/api/v1/knowledge.py
backend/app/services/prompt_service.py
backend/tests/test_knowledge_normalization.py
backend/tests/test_wiki_generate_material_scope.py
frontend/public/stitch-pages/knowledge.html
docs/当前实现基线.md
```

明确不修改：

```text
现有 Stitch 导航与整体布局
Agent 权限边界
数据库表结构
已有 Wiki 历史版本
Docker 配置
```

