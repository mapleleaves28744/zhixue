# 智学工坊：LLM Wiki 学习空间设计

文档版本：V1.0  
适用位置：`docs/LLM Wiki学习空间设计.md`  
适用对象：产品设计、前端开发、后端开发、数据库设计、RAG 设计、多智能体设计、比赛答辩材料整理  
项目名称：智学工坊

---

# 1. LLM Wiki 的定义

## 1.1 定义

智学工坊中的 **LLM Wiki 学习空间**，是由大模型和多智能体协助学生持续整理、更新、连接和复用学习内容的结构化个人知识空间。

它不是普通笔记，也不是简单的 RAG 文档库，而是将课程资料、学生笔记、AI 生成资源、智能问答结果、错题总结、学习诊断结果和学习路径统一沉淀为可阅读、可追溯、可更新、可链接、可推荐的 Wiki 页面体系。

一句话定义：

> LLM Wiki 是学生个人课程学习知识库的结构化表达层，负责把零散学习资料变成可持续成长的知识点页面和个人学习知识图谱。

## 1.2 核心目标

LLM Wiki 需要实现以下目标：

1. 把课程资料整理成知识点页面；
2. 把学生笔记整理成结构化 Wiki；
3. 把 AI 生成的学习资源沉淀到 Wiki；
4. 把错题、答疑、诊断结果关联到知识点；
5. 让学生逐步形成自己的个人学习知识图谱；
6. 为智能问答、资源生成、学习诊断、路径推荐提供结构化上下文；
7. 支持来源追溯、版本管理、人工编辑和 AI 补全；
8. 支持知识点关系可视化，帮助学生理解课程结构。

## 1.3 设计原则

| 原则 | 说明 |
|---|---|
| 知识点中心 | 以知识点页面作为 Wiki 的基本单元 |
| 来源可追溯 | 每段 AI 整理内容应尽量绑定来源资料、问答、错题或笔记 |
| 人机协同 | AI 负责生成和整理，学生负责确认、编辑和收藏 |
| 可版本化 | 页面修改需要保留历史版本，支持回滚 |
| 可关联 | 页面之间通过前置、包含、易混、应用等关系连接 |
| 可个性化 | 同一课程下，不同学生可以形成不同的个人 Wiki |
| 可服务学习闭环 | Wiki 不只是展示内容，还要支撑问答、练习、诊断和推荐 |

---

# 2. 它和普通笔记的区别

普通笔记通常是学生手动记录的线性文本，内容零散，结构不稳定，难以自动用于问答、推荐和诊断。

LLM Wiki 与普通笔记的区别如下：

| 对比项 | 普通笔记 | LLM Wiki 学习空间 |
|---|---|---|
| 组织方式 | 按时间或文件记录 | 按课程、章节、知识点组织 |
| 内容来源 | 主要靠学生手写 | 课程资料、学生笔记、AI 生成、错题、问答、诊断共同沉淀 |
| 结构化程度 | 弱结构 | 固定字段和页面模板 |
| 知识关系 | 通常没有明确关系 | 支持前置、包含、易混、应用、推荐学习顺序等关系 |
| 可追溯性 | 很少记录来源 | 页面内容绑定来源资料、页码、问答、错题 |
| 可复用性 | 主要供学生阅读 | 同时供学生阅读、RAG 检索、资源生成、学习诊断使用 |
| 可更新性 | 手动更新 | 支持 AI 自动补全、学生编辑、版本管理 |
| 个性化程度 | 取决于学生整理能力 | 根据学生画像、薄弱点、错题和学习历史动态调整 |
| 展示形式 | 文本为主 | 页面、卡片、关系图谱、资源列表、诊断关联 |

---

# 3. 它和 RAG 知识库的区别

RAG 知识库主要用于检索原始资料片段，帮助大模型回答问题。LLM Wiki 则是把原始资料和学习过程整理成长期可维护的结构化知识空间。

| 对比项 | RAG 知识库 | LLM Wiki 学习空间 |
|---|---|---|
| 核心对象 | 文档切片、向量、引用片段 | Wiki 页面、知识点、关系、版本 |
| 主要作用 | 查询时检索资料 | 长期沉淀和组织知识 |
| 面向对象 | 大模型上下文 | 学生和大模型共同使用 |
| 数据形态 | chunk + embedding | 页面 + 字段 + 关系 + 来源 + 版本 |
| 更新方式 | 文档上传后切片入库 | 学习过程中持续更新 |
| 可读性 | 对学生不友好 | 学生可以直接阅读和编辑 |
| 个性化 | 较弱 | 强，受学生画像、错题和学习路径影响 |
| 典型用途 | 智能问答引用依据 | 学习空间、知识图谱、资源沉淀、诊断依据 |

## 3.1 两者关系

RAG 与 LLM Wiki 不是替代关系，而是协作关系：

```text
原始课程资料
  → RAG：切片、向量化、检索证据
  → LLM Wiki：抽取知识点、生成页面、组织关系

学生提问
  → RAG 提供原文证据
  → LLM Wiki 提供结构化知识
  → 学生画像提供个性化上下文
  → 大模型生成回答
```

---

# 4. 它在本项目中的作用

LLM Wiki 在智学工坊中承担“知识组织底座”的作用。

## 4.1 对学生的作用

1. 形成个人课程知识库；
2. 把零散资料整理成知识点页面；
3. 快速查看知识点解释、例题、错题和资源；
4. 通过关系图谱理解知识结构；
5. 在复习时快速定位薄弱点；
6. 将 AI 问答和生成资源长期保存。

## 4.2 对智能问答的作用

1. 提供结构化上下文；
2. 提供知识点级别的引用；
3. 提供关联知识点推荐；
4. 减少模型重复解释；
5. 让问答结果可以沉淀回 Wiki。

## 4.3 对个性化资源生成的作用

1. 提供当前知识点基础内容；
2. 提供前置知识；
3. 提供常见错误；
4. 提供学生已有笔记；
5. 提供历史 AI 生成资源；
6. 支持把新资源保存回 Wiki。

## 4.4 对学习诊断的作用

1. 将错题绑定到知识点页面；
2. 将薄弱知识点显示在 Wiki 页面；
3. 将诊断结论沉淀到相关知识点；
4. 根据页面访问和练习结果判断学习困难；
5. 支持生成知识点掌握度图谱。

## 4.5 对学习路径推荐的作用

1. 根据知识点关系生成学习路径；
2. 根据前置关系推荐补弱顺序；
3. 根据易混关系推荐对比学习；
4. 根据学生掌握度调整路径节点优先级。

---

# 5. Wiki 页面类型

LLM Wiki 由多种页面组成，不同页面服务不同学习场景。

## 5.1 课程首页

课程首页是某门课程的 Wiki 入口。

用途：

1. 展示课程简介；
2. 展示章节结构；
3. 展示核心知识点；
4. 展示课程知识图谱入口；
5. 展示学习进度；
6. 展示薄弱章节；
7. 展示最近更新的 Wiki 页面。

示例：

```text
数据结构课程首页
├── 课程简介
├── 学习目标
├── 章节目录
├── 核心知识点
├── 我的学习进度
├── 薄弱知识点
├── 推荐学习路径
└── 最近更新页面
```

## 5.2 知识点页面

知识点页面是 LLM Wiki 的核心页面。

用途：

1. 解释单个知识点；
2. 展示前置知识；
3. 展示核心概念；
4. 展示例题和代码；
5. 展示常见错误；
6. 展示关联问答；
7. 展示关联错题；
8. 展示学生掌握度。

示例：

```text
知识点页面：递归调用栈
```

## 5.3 概念解释页面

概念解释页面适合解释一个较小概念或易混概念。

用途：

1. 解释术语；
2. 对比相似概念；
3. 提供简单示例；
4. 作为知识点页面的补充页面。

示例：

```text
概念解释页面：后进先出
概念解释页面：函数栈帧
概念解释页面：循环队列判满条件
```

## 5.4 错题总结页面

错题总结页面围绕某个知识点或某类错误组织。

用途：

1. 汇总学生在某知识点下的错题；
2. 归纳错因；
3. 生成纠错建议；
4. 推荐针对性练习；
5. 关联到知识点页面。

示例：

```text
错题总结页面：递归终止条件常见错误
```

## 5.5 学习资源页面

学习资源页面用于保存 AI 生成或学生收藏的学习资源。

资源类型包括：

1. 个性化讲解；
2. 例题解析；
3. 复习卡片；
4. 考前总结；
5. 对比表；
6. 实验指导；
7. 代码示例。

## 5.6 学习路径页面

学习路径页面用于展示系统推荐的学习顺序。

用途：

1. 展示路径节点；
2. 展示推荐理由；
3. 展示前置知识；
4. 展示完成状态；
5. 关联每个路径节点的 Wiki 页面。

示例：

```text
栈 → 递归调用栈 → 二叉树递归遍历 → 深度优先搜索
```

## 5.7 个人总结页面

个人总结页面用于沉淀学生自己的总结。

来源包括：

1. 学生手写笔记；
2. AI 帮学生整理的笔记；
3. 学习阶段总结；
4. 考前复习总结；
5. 项目实践总结。

---

# 6. 每个 Wiki 页面字段

## 6.1 通用字段

所有 Wiki 页面都应包含以下通用字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 页面 ID |
| user_id | UUID | 所属学生 |
| course_id | UUID | 所属课程 |
| page_type | varchar | 页面类型 |
| title | varchar | 页面标题 |
| slug | varchar | 页面路径标识 |
| summary | text | 页面摘要 |
| content | jsonb / markdown | 页面正文 |
| status | varchar | draft / active / archived |
| source_type | varchar | 来源类型 |
| created_by | varchar | ai / user / system |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |
| version_no | int | 当前版本号 |

## 6.2 知识点页面字段

| 字段 | 类型 | 说明 |
|---|---|---|
| knowledge_id | UUID | 知识点 ID |
| chapter | varchar | 所属章节 |
| difficulty | varchar | 难度 |
| importance | varchar | 重要程度 |
| mastery_score | float | 当前学生掌握度 |
| prerequisite_ids | jsonb | 前置知识点 |
| related_ids | jsonb | 关联知识点 |
| common_errors | jsonb | 常见错误 |
| examples | jsonb | 例题 |
| citations | jsonb | 来源引用 |
| personal_notes | text | 学生个人笔记 |
| generated_resources | jsonb | 关联生成资源 |

## 6.3 错题总结页面字段

| 字段 | 类型 | 说明 |
|---|---|---|
| related_knowledge_ids | jsonb | 关联知识点 |
| mistake_ids | jsonb | 关联错题 |
| error_patterns | jsonb | 错因模式 |
| correction_suggestion | text | 纠错建议 |
| recommended_exercises | jsonb | 推荐练习 |
| diagnosis_summary | text | 诊断摘要 |

## 6.4 学习路径页面字段

| 字段 | 类型 | 说明 |
|---|---|---|
| path_id | UUID | 学习路径 ID |
| path_nodes | jsonb | 路径节点 |
| target_goal | varchar | 学习目标 |
| reason | text | 推荐理由 |
| progress | float | 完成进度 |
| status | varchar | active / completed / archived |

---

# 7. Wiki 页面结构模板

## 7.1 课程首页模板

```markdown
# 课程名称

## 1. 课程简介

## 2. 学习目标

## 3. 章节目录

## 4. 核心知识点

## 5. 知识图谱

## 6. 我的学习进度

## 7. 薄弱知识点

## 8. 推荐学习路径

## 9. 最近更新
```

## 7.2 知识点页面模板

```markdown
# 知识点名称

## 1. 一句话解释

## 2. 所属章节

## 3. 学习目标

## 4. 前置知识

## 5. 核心概念

## 6. 关键公式 / 代码 / 图示说明

## 7. 典型例题

## 8. 常见错误

## 9. 与其他知识点的关系

## 10. 我的错题

## 11. AI 生成学习资源

## 12. 我的个人笔记

## 13. 来源引用

## 14. 页面版本记录
```

## 7.3 概念解释页面模板

```markdown
# 概念名称

## 1. 简要定义

## 2. 通俗解释

## 3. 示例

## 4. 易混概念

## 5. 所属知识点

## 6. 来源引用
```

## 7.4 错题总结页面模板

```markdown
# 错题总结：主题名称

## 1. 关联知识点

## 2. 错题列表

## 3. 错因归纳

## 4. 正确解法

## 5. 易错提醒

## 6. 针对性练习

## 7. 复习建议
```

## 7.5 学习资源页面模板

```markdown
# 资源标题

## 1. 资源类型

## 2. 适用知识点

## 3. 适用学生状态

## 4. 正文内容

## 5. 使用建议

## 6. 来源依据

## 7. 保存时间
```

## 7.6 学习路径页面模板

```markdown
# 学习路径名称

## 1. 学习目标

## 2. 推荐理由

## 3. 路径节点

## 4. 每个节点的学习任务

## 5. 关联 Wiki 页面

## 6. 完成状态

## 7. 下一步建议
```

---

# 8. Wiki 链接规则

Wiki 链接规则用于将页面连接成知识网络。

## 8.1 自动链接规则

系统应在以下情况下自动建立链接：

1. 页面正文提到已有知识点时，自动链接到对应页面；
2. 一个知识点依赖另一个知识点时，建立前置链接；
3. 两个概念容易混淆时，建立易混链接；
4. 错题涉及某个知识点时，错题总结页面链接到知识点页面；
5. 生成资源服务某个知识点时，资源页面链接到知识点页面；
6. 学习路径包含某个知识点时，路径节点链接到知识点页面；
7. 问答内容被保存到 Wiki 时，链接到相关知识点页面。

## 8.2 链接格式

Markdown 中可使用：

```markdown
[[栈]]
[[递归调用栈]]
[[二叉树遍历]]
```

前端渲染时将其转为内部页面链接。

## 8.3 链接类型

| 链接类型 | 说明 |
|---|---|
| inline_link | 页面正文中的普通链接 |
| relation_link | 知识点关系链接 |
| source_link | 来源引用链接 |
| mistake_link | 错题关联链接 |
| resource_link | 学习资源关联链接 |
| path_link | 学习路径节点链接 |

## 8.4 链接校验

系统应定期检查：

1. 是否存在指向不存在页面的链接；
2. 是否存在重复链接；
3. 是否存在关系类型缺失；
4. 是否存在孤立知识点页面；
5. 是否存在没有来源的 AI 生成内容。

---

# 9. 知识点关系类型

## 9.1 基础关系类型

| 关系类型 | 英文字段 | 说明 |
|---|---|---|
| 前置知识 | prerequisite | 学习 A 前需要先掌握 B |
| 包含关系 | contains | A 包含 B |
| 属于关系 | belongs_to | B 属于 A |
| 相似关系 | similar | A 与 B 概念相似 |
| 易混关系 | confused_with | A 与 B 容易混淆 |
| 支撑理解 | supports | A 有助于理解 B |
| 应用关系 | applied_to | A 可应用于 B |
| 后续学习 | next | 学完 A 后推荐学习 B |
| 例题关联 | example_of | 某题是某知识点例题 |
| 错题关联 | mistake_of | 某错题关联某知识点 |
| 资源关联 | resource_for | 某资源服务于某知识点 |

## 9.2 数据结构课程示例

```text
时间复杂度 prerequisite 顺序表
线性表 contains 顺序表
线性表 contains 单链表
顺序表 confused_with 单链表
栈 supports 递归调用栈
递归调用栈 supports 二叉树递归遍历
队列 supports 广度优先搜索
栈 supports 深度优先搜索
图遍历 contains 深度优先搜索
图遍历 contains 广度优先搜索
```

---

# 10. Wiki 自动更新流程

Wiki 自动更新由多智能体协作完成。

## 10.1 资料上传触发更新

```text
学生上传课程资料
  → 文档解析 Agent 提取文本
  → 知识抽取 Agent 抽取知识点
  → Wiki 构建 Agent 生成页面草稿
  → 来源追溯模块绑定资料来源
  → 关系抽取模块建立知识点关系
  → 质量校验 Agent 检查页面结构
  → 页面进入 draft 或 active 状态
```

## 10.2 问答后触发更新

```text
学生进行智能问答
  → 系统识别问题关联知识点
  → 问答结果带引用生成
  → 学生选择“保存到 Wiki”
  → 系统将回答整理为页面小节
  → 创建 Wiki 页面新版本
```

## 10.3 练习后触发更新

```text
学生完成练习
  → 系统批改答案
  → 学习诊断 Agent 生成错因
  → 错题总结页面更新
  → 关联知识点页面新增“我的错题”
  → 学生画像同步更新
```

## 10.4 资源生成后触发更新

```text
学生生成个性化资源
  → 资源生成 Agent 生成讲解或卡片
  → 质量校验 Agent 检查来源和结构
  → 学生点击保存
  → 学习资源页面生成
  → 对应知识点页面建立 resource_for 关系
```

## 10.5 诊断后触发更新

```text
学习诊断完成
  → 找出薄弱知识点
  → 更新知识点页面掌握度
  → 在页面中展示诊断摘要
  → 推荐补充资源和学习路径
```

---

# 11. Wiki 人工编辑流程

LLM Wiki 需要支持学生人工编辑，避免完全依赖 AI。

## 11.1 编辑入口

学生可在以下位置编辑：

1. Wiki 页面正文；
2. 个人笔记区域；
3. 页面标题；
4. 常见错误；
5. 例题备注；
6. 关系链接；
7. AI 生成内容确认状态。

## 11.2 编辑流程

```text
学生打开 Wiki 页面
  → 点击编辑
  → 修改页面内容
  → 系统生成变更 diff
  → 学生填写修改说明，可选
  → 保存新版本
  → 原版本进入历史版本
```

## 11.3 编辑权限

| 用户 | 权限 |
|---|---|
| 学生 | 可编辑自己的个人 Wiki |
| 管理员 | 可编辑公共课程模板 Wiki |
| Agent | 只能创建草稿或建议，不能覆盖学生手动内容 |

## 11.4 冲突处理

如果 AI 更新和学生手动编辑冲突：

1. 学生手动编辑优先；
2. AI 更新作为建议保留；
3. 页面展示“存在 AI 建议未合并”；
4. 学生可选择接受、拒绝或部分合并。

---

# 12. Wiki 版本管理

## 12.1 版本生成时机

以下操作需要生成新版本：

1. AI 生成新页面；
2. AI 补全页面内容；
3. 学生编辑页面；
4. 系统保存问答结果到页面；
5. 系统保存资源到页面；
6. 系统更新错题总结；
7. 系统调整页面关系；
8. 页面回滚。

## 12.2 版本字段

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 版本 ID |
| page_id | UUID | 页面 ID |
| version_no | int | 版本号 |
| title | varchar | 页面标题 |
| content_snapshot | jsonb / text | 页面内容快照 |
| change_summary | text | 变更摘要 |
| changed_by | varchar | user / ai / system / admin |
| change_type | varchar | create / update / merge / rollback |
| source_refs | jsonb | 来源引用 |
| created_at | timestamp | 创建时间 |

## 12.3 版本状态

| 状态 | 说明 |
|---|---|
| active | 当前生效版本 |
| history | 历史版本 |
| rollbacked | 已被回滚 |
| draft | 草稿版本 |

## 12.4 回滚规则

1. 学生可以回滚自己的 Wiki 页面；
2. 回滚操作生成新版本，而不是删除历史版本；
3. 回滚后需要记录回滚原因；
4. 被回滚版本仍然保留；
5. AI 生成内容回滚后不得自动再次覆盖。

---

# 13. Wiki 来源追溯

来源追溯是 LLM Wiki 的可信基础。

## 13.1 来源类型

| 来源类型 | 说明 |
|---|---|
| document | 课程资料 |
| note | 学生笔记 |
| chat | 智能问答 |
| exercise | 练习题 |
| mistake | 错题记录 |
| diagnosis | 学习诊断 |
| resource | AI 生成资源 |
| manual | 学生手动编辑 |

## 13.2 来源字段

| 字段 | 类型 | 说明 |
|---|---|---|
| source_id | UUID | 来源 ID |
| source_type | varchar | 来源类型 |
| page_id | UUID | Wiki 页面 ID |
| section_key | varchar | 页面小节 |
| document_id | UUID | 文档 ID |
| chunk_id | UUID | 文档切片 ID |
| quote_text | text | 引用原文 |
| confidence | float | 置信度 |
| created_at | timestamp | 创建时间 |

## 13.3 前端展示方式

在 Wiki 页面中，来源可用以下形式展示：

```text
来源：数据结构第 3 章课件，第 12 页
来源：学生 2026-05-20 智能问答记录
来源：错题 Q003，错误标签：递归终止条件不清
```

## 13.4 无来源内容标记

如果内容由 AI 推断生成，且没有直接资料来源，应标记为：

```text
AI 推断内容，建议核对资料
```

这样可以降低幻觉风险。

---

# 14. Wiki 矛盾检测

## 14.1 检测目标

矛盾检测用于发现 Wiki 页面中可能存在的不一致内容。

## 14.2 检测对象

1. 同一知识点不同资料中的定义不一致；
2. AI 生成内容与原始资料冲突；
3. 页面前后表述不一致；
4. 知识点关系冲突；
5. 错题解析与 Wiki 概念解释冲突；
6. 学生手动笔记与资料内容冲突。

## 14.3 检测流程

```text
定时扫描 Wiki 页面
  → 抽取关键断言
  → 对比来源资料和历史版本
  → 调用质量校验 Agent 判断是否冲突
  → 生成矛盾检测报告
  → 页面显示风险提示
  → 学生或管理员确认处理
```

## 14.4 矛盾类型

| 类型 | 示例 |
|---|---|
| definition_conflict | 同一概念定义不一致 |
| relation_conflict | A 是 B 的前置知识，同时又被标记为 B 的后续知识 |
| answer_conflict | 问答结果与 Wiki 页面内容不一致 |
| source_conflict | 不同资料来源给出不同说法 |
| manual_ai_conflict | 学生笔记和 AI 补充内容冲突 |

## 14.5 MVP 处理方式

MVP 不需要做复杂自动矛盾推理，可以先做：

1. 检测同名知识点重复页面；
2. 检测无来源 AI 内容；
3. 检测前置关系循环；
4. 检测页面字段缺失；
5. 由 LLM 对页面内容做一次简单一致性检查。

---

# 15. Wiki 与学生画像的关系

LLM Wiki 与学生画像是双向关系。

## 15.1 学生画像影响 Wiki

学生画像会影响 Wiki 的展示和更新。

例如：

| 学生画像 | Wiki 变化 |
|---|---|
| 递归薄弱 | 递归页面突出显示“常见错误”和“补弱资源” |
| 偏好代码示例 | Wiki 页面优先展示代码小节 |
| 基础薄弱 | 页面显示前置知识提醒 |
| 考试复习目标 | 页面显示高频考点和易错题 |
| 视觉型学习偏好 | 页面推荐图示资源 |

## 15.2 Wiki 影响学生画像

Wiki 使用行为会反过来更新画像。

例如：

| Wiki 行为 | 画像变化 |
|---|---|
| 频繁浏览某知识点页面 | 说明该知识点可能是关注点或薄弱点 |
| 收藏某类资源 | 更新资源偏好 |
| 手动补充某知识点笔记 | 增加该知识点学习活跃度 |
| 多次查看错题总结 | 增强错因模式置信度 |
| 完成 Wiki 推荐练习 | 更新掌握度 |

---

# 16. Wiki 与资源生成的关系

## 16.1 Wiki 为资源生成提供上下文

资源生成 Agent 在生成资源时读取：

1. 知识点页面；
2. 前置知识；
3. 常见错误；
4. 学生错题；
5. 学生画像；
6. 已有资源；
7. 来源资料。

## 16.2 资源生成结果沉淀回 Wiki

AI 生成的资源不应只停留在一次性结果页，而应支持保存到 Wiki。

可保存内容：

1. 讲解；
2. 总结；
3. 例题；
4. 复习卡片；
5. 对比表；
6. 错题解析；
7. 代码示例；
8. 学习路径说明。

## 16.3 资源去重

保存到 Wiki 前应检查：

1. 是否与已有资源重复；
2. 是否已经存在类似例题；
3. 是否已经存在相同解释；
4. 是否有来源依据；
5. 是否需要追加到已有页面，而不是新建页面。

---

# 17. Wiki 与学习诊断的关系

## 17.1 Wiki 支撑诊断

学习诊断需要读取 Wiki 中的：

1. 知识点结构；
2. 前置关系；
3. 易混关系；
4. 常见错误；
5. 关联错题；
6. 资源使用记录；
7. 页面掌握度。

## 17.2 诊断结果反向更新 Wiki

学习诊断完成后，应更新 Wiki：

1. 在知识点页面显示当前掌握度；
2. 在页面中添加“我的薄弱点”标记；
3. 关联错题总结页面；
4. 添加推荐练习；
5. 添加复习建议；
6. 更新学习路径页面。

## 17.3 示例

```text
诊断发现：
学生在“循环队列判满条件”上错误率高。

Wiki 更新：
1. 循环队列页面标记为薄弱；
2. 常见错误新增“front == rear 条件理解错误”；
3. 关联 3 道错题；
4. 推荐复习“队列基本概念”和“循环队列数组实现”。
```

---

# 18. Wiki 与多智能体的关系

## 18.1 参与 Wiki 的 Agent

| Agent | 职责 |
|---|---|
| DocumentAgent | 解析课程资料 |
| KnowledgeExtractAgent | 抽取知识点和关系 |
| WikiBuildAgent | 生成 Wiki 页面 |
| WikiUpdateAgent | 更新页面内容 |
| WikiRelationAgent | 建立和维护页面关系 |
| ResourceAgent | 生成可沉淀到 Wiki 的资源 |
| DiagnosisAgent | 将诊断结果关联到 Wiki |
| EvolutionAgent | 根据学习行为提出 Wiki 结构优化建议 |
| QualityCheckAgent | 检查来源、结构完整性和矛盾 |
| RouterAgent | 判断用户请求是否涉及 Wiki 操作 |

## 18.2 Agent 协作流程

```text
上传资料
  → DocumentAgent 解析
  → KnowledgeExtractAgent 抽取知识点
  → WikiBuildAgent 生成页面
  → WikiRelationAgent 建立关系
  → QualityCheckAgent 校验
  → WikiService 入库
```

```text
学生问答后保存
  → QAAgent 生成回答
  → QualityCheckAgent 校验
  → WikiUpdateAgent 整理为页面小节
  → WikiService 创建新版本
```

```text
学习诊断后更新
  → DiagnosisAgent 识别薄弱点
  → WikiUpdateAgent 更新页面诊断区域
  → WikiRelationAgent 推荐补弱路径
```

---

# 19. 数据库表设计建议

## 19.1 wiki_pages：Wiki 页面表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 页面 ID |
| user_id | UUID | 所属学生 |
| course_id | UUID | 所属课程 |
| knowledge_id | UUID | 关联知识点，可为空 |
| page_type | varchar | 页面类型 |
| title | varchar | 页面标题 |
| slug | varchar | 页面路径 |
| summary | text | 页面摘要 |
| content | jsonb | 页面结构化内容 |
| markdown_content | text | Markdown 正文 |
| status | varchar | draft / active / archived |
| created_by | varchar | ai / user / system / admin |
| version_no | int | 当前版本号 |
| created_at | timestamp | 创建时间 |
| updated_at | timestamp | 更新时间 |

## 19.2 wiki_page_versions：Wiki 页面版本表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 版本 ID |
| page_id | UUID | 页面 ID |
| version_no | int | 版本号 |
| content_snapshot | jsonb | 内容快照 |
| markdown_snapshot | text | Markdown 快照 |
| change_summary | text | 变更摘要 |
| changed_by | varchar | 修改者 |
| change_type | varchar | create / update / rollback / merge |
| created_at | timestamp | 创建时间 |

## 19.3 wiki_links：Wiki 关系表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 关系 ID |
| course_id | UUID | 课程 ID |
| user_id | UUID | 学生 ID |
| source_page_id | UUID | 起点页面 |
| target_page_id | UUID | 终点页面 |
| relation_type | varchar | 关系类型 |
| description | text | 关系说明 |
| confidence | float | 置信度 |
| created_by | varchar | ai / user / system |
| status | varchar | active / rejected |
| created_at | timestamp | 创建时间 |

## 19.4 wiki_sources：Wiki 来源表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 来源 ID |
| page_id | UUID | 页面 ID |
| section_key | varchar | 页面小节 |
| source_type | varchar | 来源类型 |
| source_ref_id | UUID | 来源对象 ID |
| document_id | UUID | 文档 ID |
| chunk_id | UUID | 文档切片 ID |
| quote_text | text | 引用原文 |
| confidence | float | 置信度 |
| created_at | timestamp | 创建时间 |

## 19.5 wiki_edit_suggestions：Wiki 编辑建议表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 建议 ID |
| page_id | UUID | 页面 ID |
| suggestion_type | varchar | 补全 / 修改 / 合并 / 拆分 / 建立关系 |
| suggestion_content | jsonb | 建议内容 |
| reason | text | 建议原因 |
| evidence | jsonb | 依据 |
| status | varchar | pending / accepted / rejected |
| created_by_agent | varchar | 生成建议的 Agent |
| created_at | timestamp | 创建时间 |

## 19.6 wiki_conflicts：Wiki 矛盾检测表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 冲突 ID |
| page_id | UUID | 页面 ID |
| conflict_type | varchar | 冲突类型 |
| conflict_description | text | 冲突说明 |
| involved_sources | jsonb | 涉及来源 |
| severity | varchar | low / medium / high |
| status | varchar | unresolved / resolved / ignored |
| created_at | timestamp | 创建时间 |

## 19.7 knowledge_points：知识点表

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 知识点 ID |
| course_id | UUID | 课程 ID |
| name | varchar | 知识点名称 |
| chapter | varchar | 所属章节 |
| description | text | 知识点说明 |
| difficulty | varchar | 难度 |
| importance | varchar | 重要度 |
| created_at | timestamp | 创建时间 |

---

# 20. 后端 API 设计建议

## 20.1 Wiki 页面 API

### 创建 Wiki 页面

```http
POST /api/v1/wiki/pages
```

请求体：

```json
{
  "course_id": "c_001",
  "page_type": "knowledge",
  "title": "递归调用栈",
  "knowledge_id": "k_001",
  "content": {}
}
```

### 获取 Wiki 页面详情

```http
GET /api/v1/wiki/pages/{page_id}
```

### 获取课程 Wiki 页面列表

```http
GET /api/v1/wiki/pages?course_id=c_001&page_type=knowledge
```

### 更新 Wiki 页面

```http
PUT /api/v1/wiki/pages/{page_id}
```

### 删除或归档 Wiki 页面

```http
DELETE /api/v1/wiki/pages/{page_id}
```

## 20.2 Wiki 版本 API

### 获取页面版本列表

```http
GET /api/v1/wiki/pages/{page_id}/versions
```

### 获取指定版本

```http
GET /api/v1/wiki/pages/{page_id}/versions/{version_id}
```

### 回滚到指定版本

```http
POST /api/v1/wiki/pages/{page_id}/rollback
```

请求体：

```json
{
  "target_version_id": "wv_001",
  "reason": "AI 补全内容不准确，恢复到学生手动版本"
}
```

## 20.3 Wiki 关系 API

### 获取页面关系

```http
GET /api/v1/wiki/pages/{page_id}/relations
```

### 创建关系

```http
POST /api/v1/wiki/relations
```

请求体：

```json
{
  "course_id": "c_001",
  "source_page_id": "p_stack",
  "target_page_id": "p_recursion_stack",
  "relation_type": "supports",
  "description": "理解栈有助于理解递归调用栈"
}
```

### 删除关系

```http
DELETE /api/v1/wiki/relations/{relation_id}
```

## 20.4 Wiki 来源 API

### 获取页面来源

```http
GET /api/v1/wiki/pages/{page_id}/sources
```

### 添加来源

```http
POST /api/v1/wiki/pages/{page_id}/sources
```

## 20.5 Wiki 自动生成 API

### 从文档生成 Wiki

```http
POST /api/v1/wiki/generate-from-document
```

请求体：

```json
{
  "course_id": "c_001",
  "document_id": "d_001"
}
```

### 从问答保存到 Wiki

```http
POST /api/v1/wiki/save-from-chat
```

请求体：

```json
{
  "course_id": "c_001",
  "message_id": "m_001",
  "target_page_id": "p_001",
  "section_key": "ai_supplement"
}
```

### 从资源保存到 Wiki

```http
POST /api/v1/wiki/save-from-resource
```

## 20.6 Wiki 质量检查 API

### 检查页面完整度

```http
POST /api/v1/wiki/pages/{page_id}/health-check
```

### 检查页面矛盾

```http
POST /api/v1/wiki/pages/{page_id}/conflict-check
```

### 获取编辑建议

```http
GET /api/v1/wiki/pages/{page_id}/suggestions
```

### 接受编辑建议

```http
POST /api/v1/wiki/suggestions/{suggestion_id}/accept
```

### 拒绝编辑建议

```http
POST /api/v1/wiki/suggestions/{suggestion_id}/reject
```

---

# 21. 前端页面设计建议

## 21.1 Wiki 课程首页

页面模块：

1. 课程标题与简介；
2. 学习进度卡片；
3. 章节目录；
4. 核心知识点列表；
5. 知识图谱入口；
6. 薄弱知识点提醒；
7. 推荐学习路径；
8. 最近更新页面；
9. 最近保存资源。

## 21.2 Wiki 页面详情页

页面布局建议：

```text
左侧：页面目录 / 章节导航
中间：Wiki 页面正文
右侧：来源引用 / 关联知识点 / 学习状态
底部：版本历史 / AI 建议 / 关联资源
```

页面功能：

1. 查看页面；
2. 编辑页面；
3. 保存版本；
4. 查看来源；
5. 查看关联知识点；
6. 查看关联错题；
7. 保存 AI 内容到页面；
8. 查看版本历史；
9. 回滚版本；
10. 接受或拒绝 AI 建议。

## 21.3 知识图谱页面

功能：

1. 展示知识点节点；
2. 展示关系边；
3. 按关系类型筛选；
4. 按掌握度着色；
5. 点击节点进入 Wiki 页面；
6. 显示推荐学习路径；
7. 高亮薄弱知识点。

## 21.4 错题总结页面

功能：

1. 展示错题列表；
2. 展示错因分类；
3. 展示关联知识点；
4. 展示纠错建议；
5. 生成针对性练习；
6. 保存总结到 Wiki。

## 21.5 Wiki 编辑器

建议支持：

1. Markdown 编辑；
2. 分块编辑；
3. AI 补全按钮；
4. 来源插入；
5. 内链插入；
6. 保存为新版本；
7. 预览模式。

## 21.6 AI 建议面板

展示：

1. 建议类型；
2. 建议内容；
3. 建议原因；
4. 依据来源；
5. 接受按钮；
6. 拒绝按钮；
7. 稍后处理按钮。

---

# 22. MVP 实现方案

MVP 阶段目标是实现一个可演示的 LLM Wiki 闭环：

```text
上传课程资料 → 解析知识点 → 生成 Wiki 页面 → 智能问答引用 Wiki → AI 资源保存到 Wiki → 错题关联 Wiki
```

## 22.1 MVP 必做功能

| 功能 | MVP 实现方式 |
|---|---|
| 课程 Wiki 首页 | 显示课程介绍、章节、知识点列表 |
| 知识点页面 | 按固定模板展示知识点内容 |
| 自动生成页面 | 从资料切片中抽取知识点并生成页面 |
| 页面来源追溯 | 页面显示引用文档和切片 |
| 页面编辑 | 学生可编辑 Markdown 内容 |
| 页面版本 | 每次保存生成新版本 |
| 页面关系 | 支持前置、相关、易混三类关系 |
| 保存问答到 Wiki | 学生可将 AI 回答保存到指定页面 |
| 保存资源到 Wiki | 学生可将生成资源保存到知识点页面 |
| 错题关联 Wiki | 错题记录关联到知识点页面 |
| Wiki 页面列表 | 支持按课程查看所有页面 |

## 22.2 MVP 可暂缓功能

| 功能 | 暂缓原因 |
|---|---|
| 复杂矛盾检测 | 实现成本较高 |
| 自动合并重复页面 | 容易误合并 |
| 高级知识图谱推理 | 需要较多算法工作 |
| 多人协同编辑 | 当前系统以个人学习空间为主 |
| 精细页面级权限 | MVP 用户只访问自己的 Wiki |
| AI 自动大规模重组 Wiki | 风险较高，先做建议机制 |

## 22.3 MVP 演示链路

```text
学生进入《数据结构》课程
  → 上传“栈和队列”讲义
  → 系统生成“栈”“队列”“递归调用栈”Wiki 页面
  → 学生打开“递归调用栈”页面
  → 页面显示核心概念、前置知识、例题、来源引用
  → 学生提问“递归为什么和栈有关”
  → 系统基于 Wiki 和资料回答
  → 学生点击“保存到 Wiki”
  → 页面新增 AI 补充内容并生成新版本
  → 学生做题答错
  → 错题自动关联到“递归调用栈”页面
```

## 22.4 MVP 数据结构简化建议

MVP 可以先实现以下表：

1. `wiki_pages`
2. `wiki_page_versions`
3. `wiki_links`
4. `wiki_sources`
5. `knowledge_points`

其他建议、冲突检测、健康度检查可以增强版再做。

---

# 23. 增强版实现方案

增强版重点体现比赛创新性和系统深度。

## 23.1 增强功能

| 功能 | 说明 |
|---|---|
| Wiki 健康度检查 | 检查页面是否缺少定义、例题、来源、关联知识点 |
| Wiki 矛盾检测 | 检查页面内部或不同来源之间是否冲突 |
| AI 页面补全 | AI 根据资料和错题补全缺失内容 |
| 页面重复检测 | 检测相似页面并提出合并建议 |
| 知识图谱可视化 | 展示知识点关系网络 |
| 个性化页面排序 | 根据学生薄弱点优先展示相关内容 |
| Wiki 与画像联动 | 页面显示学生掌握度、薄弱原因和推荐资源 |
| Wiki 结构进化 | 自进化 Agent 提出页面拆分、合并、关系调整建议 |
| 版本 diff 展示 | 对比两个版本内容差异 |
| 来源可信度评分 | 根据来源类型和置信度展示内容可信度 |

## 23.2 增强版比赛展示重点

1. 展示 AI 如何从资料自动生成 Wiki；
2. 展示知识点之间的关系图；
3. 展示错题如何回流到知识点页面；
4. 展示问答结果如何沉淀到 Wiki；
5. 展示 Wiki 页面版本变化；
6. 展示 AI 检测 Wiki 缺失内容；
7. 展示 Wiki 如何根据学生画像突出薄弱点；
8. 展示系统如何逐步形成个人学习知识图谱。

---

# 24. 与其他系统模块的接口关系

## 24.1 与课程资料系统

输入：

1. 课程资料；
2. 文档切片；
3. 文件元数据；
4. 文档解析结果。

输出：

1. 知识点页面；
2. 页面来源；
3. 知识点列表。

## 24.2 与 RAG 系统

输入：

1. RAG 检索结果；
2. 引用片段；
3. 文档 chunk。

输出：

1. 结构化 Wiki 页面；
2. 可检索的 Wiki 内容；
3. 问答上下文。

## 24.3 与智能问答系统

输入：

1. 学生问题；
2. 问答结果；
3. 引用来源；
4. 相关知识点。

输出：

1. 保存到 Wiki 的回答；
2. 更新后的页面版本；
3. 关联知识点推荐。

## 24.4 与资源生成系统

输入：

1. 个性化讲解；
2. 例题；
3. 总结；
4. 复习卡片。

输出：

1. 学习资源页面；
2. 知识点页面资源区；
3. 页面版本更新。

## 24.5 与学习诊断系统

输入：

1. 错题；
2. 错因；
3. 掌握度；
4. 薄弱知识点。

输出：

1. 页面薄弱标记；
2. 错题总结页面；
3. 推荐补弱资源。

## 24.6 与自进化系统

输入：

1. Wiki 使用行为；
2. 页面浏览记录；
3. 页面编辑记录；
4. 页面缺失检测；
5. 错题关联情况。

输出：

1. Wiki 页面补全建议；
2. 知识组织结构优化建议；
3. 页面排序个性化建议；
4. 关系调整建议。

---

# 25. 比赛答辩表述建议

可以这样介绍：

> 智学工坊中的 LLM Wiki 不是普通笔记，也不是简单文档检索库。它是一个由 AI 协助学生持续整理和更新的结构化学习知识空间。系统会把课程资料、学生笔记、AI 问答、个性化资源、错题和诊断结果沉淀到知识点页面，并通过前置、易混、应用等关系连接成个人学习知识图谱。这样学生越学，Wiki 越完整；系统越了解学生，推荐和资源生成也越个性化。

答辩时重点展示：

1. 一份课程资料如何变成多个 Wiki 页面；
2. Wiki 页面如何显示来源引用；
3. 页面之间如何形成知识关系；
4. AI 回答如何保存到 Wiki；
5. 错题如何关联到知识点；
6. 诊断结果如何影响 Wiki 展示；
7. Wiki 如何支撑后续问答、资源生成和学习路径推荐。

---

# 26. 最终结论

LLM Wiki 学习空间是智学工坊的核心创新模块之一。它让系统从“临时问答工具”升级为“长期学习空间”。

它的核心价值是：

1. 把资料变成结构化知识；
2. 把问答变成可复用内容；
3. 把错题变成诊断依据；
4. 把资源变成长期资产；
5. 把知识点连接成个人学习图谱；
6. 把学生学习过程沉淀为可持续优化的知识空间。

MVP 阶段应优先实现：

```text
课程首页 → 知识点页面 → 来源追溯 → 页面编辑 → 版本管理 → 问答/资源/错题保存到 Wiki
```

增强版阶段再实现：

```text
知识图谱可视化 → 矛盾检测 → AI 补全 → Wiki 健康度检查 → 结构进化建议 → 个性化页面展示
```
