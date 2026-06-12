# OpenMAIC 沉浸课堂与知识点讲解视频融合设计

> 文档状态：已确认设计规格  
> 日期：2026-06-13  
> 首期目标：学生在 `/assistant` 输入一句自然语言目标，即可基于课程资料和个人学习状态生成沉浸式互动课堂，并可进一步导出带配音、字幕和来源依据的知识点讲解 MP4。  
> 实施边界：本规格只描述首期融合，不包含 PBL 深度闭环、课堂互动结果回流、原生幻灯片编辑器迁移或 Docker 正式部署。

## 1. 背景与事实判断

智学工坊已经具备课程资料处理、Hybrid RAG、LLM Wiki、学生画像、长期记忆、练习诊断、自进化策略、Agent 编排、媒体资产和异步媒体任务。当前多模态链路也已经支持教学插图、互动课件、分镜和讲解视频任务，但存在两个明显不足：

1. 当前互动课件主要是安全模板，缺少成熟的沉浸式课堂播放、幻灯片讲解动作和丰富互动模拟。
2. 当前本地讲解视频主要由静态分镜卡片合成，缺少完整配音、字幕以及更丰富的视觉场景。

本地 OpenMAIC 已适配 Xiaomi MiMo V2.5、Token Plan、MiMo TTS 和 MiMo ASR，并已经提供：

- 一键课堂生成 API；
- 幻灯片、测验、互动场景和 PBL 场景；
- 图片与短视频素材生成；
- 课堂讲解动作和 TTS 音频预生成；
- 沉浸课堂播放页面。

OpenMAIC 使用 AGPL-3.0。首期采用开源工程集成与二次开发方式，保留许可证、上游来源和团队修改记录，不将实际复用描述为仅参考思路。

## 2. 首期成功标准

学生在 `/assistant` 输入：

```text
基于课程资料，为我生成一个适合初学者的 BFS 知识点讲解视频和沉浸课堂。
```

系统能够完成：

```text
课程权限校验
  -> RAG 检索课程依据
  -> 读取画像、薄弱点和学习偏好
  -> 形成最小化个性化课堂要求
  -> OpenMAIC 异步生成课堂、视觉素材和 MiMo 配音
  -> zhixue 同步进度并保存课堂产物
  -> /assistant 展示沉浸课堂入口
  -> 复用课堂场景与音频合成带字幕 MP4
  -> 保存引用、个性化理由、审核结果和 Agent 日志
```

首期交付物包括：

1. 可打开并播放的沉浸式互动课堂；
2. 可在 `/assistant` 播放和下载的知识点讲解 MP4；
3. 可查看的生成进度、来源引用、个性化理由和 Review 结果；
4. OpenMAIC 服务不可用或真实 Provider 失败时的明确失败状态。

## 3. 方案选择

### 3.1 采用方案：仓库内独立 OpenMAIC 应用

OpenMAIC 完整代码进入 zhixue 仓库，但保持独立 Next.js 应用、依赖和进程：

```text
zhixue/
├── third_party/openmaic/
│   ├── OpenMAIC 源码
│   ├── LICENSE
│   ├── UPSTREAM.md
│   └── CHANGES_ZHIXUE.md
├── backend/app/integrations/openmaic/
├── backend/app/services/immersive_classroom_service.py
└── frontend/components/assistant/
```

本地运行进程：

```text
zhixue frontend   http://127.0.0.1:3000
zhixue backend    http://127.0.0.1:8000
OpenMAIC module   http://127.0.0.1:3001
```

选择原因：

- OpenMAIC 代码可随 zhixue 仓库推送和部署；
- 保留本地 MiMo、TTS、ASR 改造；
- 避免与 zhixue 前端 React、Tailwind 和状态管理直接冲突；
- zhixue 可以通过稳定 API 契约替换或升级 OpenMAIC；
- 安全、鉴权、用户隔离和业务事实数据仍由 zhixue 掌握。

### 3.2 不采用方案

不使用 Git Submodule，因为它不能可靠携带当前未发布的本地 OpenMAIC 改造，服务器部署也更容易遗漏指定提交。

不直接将 OpenMAIC 页面、组件和状态管理合并进 `frontend/`，因为两套前端依赖和运行模型差异较大，直接合并会扩大回归风险。

不在首期自行重写完整课堂播放器，因为开发周期长，且不能充分复用现有 OpenMAIC 改造成果。

## 4. 系统职责边界

### 4.1 zhixue 是业务事实源

zhixue 负责：

- 用户身份与课程访问权限；
- 课程资料、RAG、Wiki 和引用；
- 学生画像、偏好、薄弱点和诊断；
- Agent 工具选择、任务、事件和审核；
- `generated_resources`、`media_jobs`、`media_assets`；
- 沉浸课堂和 MP4 的用户归属；
- 后续学习记录、诊断和自进化扩展。

### 4.2 OpenMAIC 是课堂生成与播放引擎

OpenMAIC 负责：

- 课堂大纲和场景生成；
- 幻灯片、测验、互动场景和讲解动作；
- 图片和短视频素材生成；
- MiMo TTS 课堂音频生成；
- 沉浸课堂持久化与播放。

OpenMAIC 不直接访问：

- zhixue PostgreSQL；
- zhixue JWT；
- 完整学生记忆；
- 其他学生数据；
- 不属于当前课堂任务的原始资料。

## 5. 后端组件设计

### 5.1 OpenMAIC Client

`backend/app/integrations/openmaic/client.py` 封装外部调用，只向 Service 暴露稳定方法：

```python
create_classroom(request) -> OpenMAICJob
get_job(job_id) -> OpenMAICJobStatus
get_classroom_manifest(classroom_id) -> ClassroomManifest
health_check() -> OpenMAICHealth
```

Client 负责：

- 超时、HTTP 错误和响应解析；
- 内部服务令牌；
- 不记录密钥和完整私有上下文；
- 将 OpenMAIC 状态映射为 zhixue 统一状态。

### 5.2 ImmersiveClassroomService

`ImmersiveClassroomService` 负责业务流程：

1. 校验当前用户可读取课程；
2. 使用现有 RAG、画像和偏好服务构建课堂 brief；
3. 对发送给 OpenMAIC 的内容进行最小化和长度限制；
4. 创建 `generated_resources` 和 `media_jobs`；
5. 调用 OpenMAIC Client 创建任务；
6. 保存 `provider_job_id` 和任务元数据；
7. 由后台 Worker 轮询进度；
8. 完成后创建课堂媒体资产和 MP4 导出任务。

### 5.3 Agent Tool

新增工具：

```text
generate_immersive_classroom
```

核心输入：

```json
{
  "course_id": "uuid",
  "topic": "BFS",
  "learning_goal": "适合初学者，重点理解队列与访问顺序",
  "generate_video_export": true,
  "enable_images": true,
  "enable_video_clips": true,
  "enable_tts": true
}
```

工具只创建异步任务并返回 artifact/job 引用，不同步等待完整课堂生成。Supervisor 对“沉浸课堂、一键课程、知识点讲解视频”等意图优先路由该工具。

### 5.4 Worker 与状态同步

复用现有 arq Worker 和 `media_jobs`：

```text
queued
  -> preparing_context
  -> generating_outlines
  -> generating_scenes
  -> generating_media
  -> generating_tts
  -> persisting_classroom
  -> exporting_video
  -> reviewing
  -> succeeded / failed
```

OpenMAIC 课堂生成成功后，即使 MP4 导出失败，课堂产物仍标记可用。MP4 导出使用独立子任务和独立错误状态，避免次要产物阻塞主交付物。

## 6. 个性化上下文设计

发送给 OpenMAIC 的请求必须是最小化课堂 brief，而不是完整数据库快照。

课堂 brief 包含：

- 课程名称和知识点主题；
- 用户显式学习目标；
- 经过截断和脱敏的 RAG 依据摘要；
- 来源标题和可追溯引用标识；
- 当前薄弱点；
- 推荐难度；
- 解释风格和资源偏好；
- 需要强调的常见错误；
- 中文输出与课堂结构要求。

不发送：

- 用户账号、邮箱、JWT；
- 与当前知识点无关的对话；
- 完整长期记忆；
- 未经筛选的全部资料正文；
- 其他课程和其他学生内容。

## 7. 沉浸课堂产物

课堂生成完成后，zhixue 创建：

- 一个 `generated_resources` 记录，资源类型使用 `interactive_courseware`；
- 一个课堂入口 `media_asset`，记录 OpenMAIC classroom ID、访问地址、场景数和来源；
- `media_job.output_payload` 保存 OpenMAIC job ID、classroom ID、场景数和生成阶段摘要；
- Agent 事件展示阶段、进度、错误和最终入口。

课堂入口优先在新标签页打开独立来源。首期不使用现有 `MediaAssetPreview` 直接加载 OpenMAIC 页面，因为当前通用 iframe 缺少适合任意互动页面的严格 sandbox 和来源隔离。

## 8. 一键知识点讲解 MP4

### 8.1 视频定义

首期“知识点讲解视频”是基于可靠课程内容制作的教学视频，不是将整个课程交给黑盒文生视频模型自由生成。

视频组成：

- OpenMAIC 课堂场景和幻灯片；
- OpenMAIC 生成或引用的教学插图、流程图和短视频片段；
- 场景中的 speech action 讲解文本；
- MiMo TTS 音频；
- 根据讲解文本生成的字幕；
- 课程标题、知识点标题和来源说明页。

### 8.2 合成流程

```text
读取 OpenMAIC classroom manifest
  -> 提取场景、讲解文本、视觉素材和 TTS 音频
  -> 确定每段音频时长
  -> 生成字幕时间轴
  -> 渲染场景帧或使用场景媒体
  -> FFmpeg/MoviePy 合成 MP4
  -> 写入 media_asset
  -> 执行多模态 Review
```

首期字幕基于已知讲解文本和音频片段顺序生成，不使用 ASR 重新识别 TTS 音频。这样可以减少识别误差，并避免无意义的重复调用。

### 8.3 图片和短视频素材

OpenMAIC 可使用其已配置图片与视频 Provider 生成课堂素材。MiMo V2.5、MiMo TTS 和 MiMo ASR 不等于图片或视频生成模型，因此真实图片和短视频片段仍依赖 OpenMAIC 中配置的对应 Provider。

未配置真实图片或视频 Provider 时：

- 沉浸课堂仍可使用文本、图表和模板场景；
- MP4 仍可使用幻灯片、Mermaid 图和 MiMo TTS 合成；
- 前端明确显示降级模式，不把模板素材描述为真实文生图或文生视频结果。

## 9. 前端设计

首期只扩展已经 React 化的 `/assistant`，不重做其他 Stitch 页面。

新增体验：

1. 用户通过自然语言触发，无需额外复杂表单；
2. Agent 时间线展示课堂准备、场景生成、媒体生成、配音、视频导出和 Review；
3. 对话中显示沉浸课堂产物卡片；
4. 课堂卡片显示标题、主题、个性化理由、引用数量、场景数量和生成状态；
5. 成功后提供“进入沉浸课堂”按钮；
6. MP4 成功后沿用现有视频资产预览组件播放；
7. MP4 失败时课堂卡片仍保持可用，并单独显示导出失败原因。

## 10. 访问控制与安全

### 10.1 用户隔离

- 所有创建、查询和产物读取必须校验当前用户；
- OpenMAIC classroom ID 不直接作为 zhixue 权限依据；
- zhixue 保存用户与 classroom ID 的绑定；
- 用户只能通过 zhixue 授权入口访问属于自己的课堂。

### 10.2 OpenMAIC 内部访问

首期为 OpenMAIC API 增加服务端共享令牌校验。浏览器不能直接调用课堂生成 API。部署环境中 OpenMAIC 生成 API 应只允许 zhixue backend 访问。

课堂播放使用短期签名访问参数或由 zhixue 授权后生成的短期入口。OpenMAIC 当前全局 `ACCESS_CODE` 不能作为多用户隔离方案。

### 10.3 HTML 与媒体安全

- OpenMAIC 运行在独立来源；
- 首期不把任意 OpenMAIC HTML 保存为同源 zhixue HTML 资产；
- 外部媒体下载执行超时、大小和内容类型校验；
- Provider 密钥只存在服务端环境；
- 日志不保存密钥、JWT 和完整学生私有上下文。

## 11. 开源合规与比赛表达

`third_party/openmaic` 必须保留：

- 上游 AGPL-3.0 `LICENSE`；
- `UPSTREAM.md`：上游仓库地址、基准提交、同步日期；
- `CHANGES_ZHIXUE.md`：MiMo、Token Plan、TTS、ASR、安全和 zhixue 集成改造；
- OpenMAIC 原有版权和许可证提示。

比赛材料统一表述：

```text
智学工坊原创实现个性化学习闭环，并基于 OpenMAIC 开源课堂引擎完成沉浸课堂能力集成与二次开发。团队完成课程 RAG 与学生画像注入、MiMo V2.5 Token Plan、MiMo TTS/ASR、用户隔离、异步任务、来源溯源、Agent 编排和知识点讲解视频导出。
```

不得表述为“沉浸课堂完全自主研发”或“仅参考 OpenMAIC 思路但未使用代码”。

## 12. 配置设计

zhixue 新增配置：

```env
OPENMAIC_ENABLED=true
OPENMAIC_BASE_URL=http://127.0.0.1:3001
OPENMAIC_INTERNAL_TOKEN=
OPENMAIC_REQUEST_TIMEOUT_SECONDS=30
OPENMAIC_JOB_MAX_WAIT_SECONDS=1800
OPENMAIC_PUBLIC_BASE_URL=http://127.0.0.1:3001
```

OpenMAIC 模块独立配置 Xiaomi MiMo、TTS、ASR、图片和视频 Provider。密钥不从前端传递，也不提交进仓库。

## 13. 错误处理与降级

| 场景 | 行为 |
|---|---|
| OpenMAIC 未启动 | 任务失败并提示课堂引擎不可用，不伪装成功 |
| OpenMAIC LLM 失败 | 保存明确错误和阶段，允许后续重试 |
| 图片 Provider 未配置 | 使用文本、图表或模板视觉并标记降级 |
| 短视频 Provider 未配置 | 不生成短视频片段，继续课堂和 MP4 合成 |
| MiMo TTS 失败 | 沉浸课堂仍可用；MP4 导出失败或生成无声降级版本时必须明确标记 |
| MP4 合成失败 | 沉浸课堂保持成功，MP4 子任务单独失败 |
| Worker 重启 | 依据 `media_jobs` 和 OpenMAIC job 状态恢复轮询 |
| OpenMAIC job 长时间无进度 | 标记超时，保留 provider job ID 供排查 |

## 14. 首期测试与验收

### 14.1 单元与集成测试

- OpenMAIC Client 响应解析、超时和错误映射；
- 课堂 brief 不包含 JWT、邮箱和无关完整记忆；
- `ImmersiveClassroomService` 校验用户课程权限；
- Agent 工具只创建异步任务；
- Worker 正确同步 OpenMAIC 阶段和进度；
- 课堂成功、MP4 失败时状态相互独立；
- 用户不能读取其他学生课堂产物；
- OpenMAIC 内部生成 API 拒绝无内部令牌请求。

### 14.2 本地运行验收

必须验证：

1. OpenMAIC 模块能够在 `third_party/openmaic` 安装、构建和启动；
2. zhixue backend、arq Worker、frontend 和 OpenMAIC 可同时本地运行；
3. `/assistant` 一句话创建课堂任务；
4. Agent 时间线能够看到生成进度；
5. 课堂生成成功后可以打开；
6. 课堂内容使用课程 RAG 引用和学生个性化信息；
7. MiMo TTS 配音可播放；
8. MP4 包含音频和字幕；
9. 无真实图片/视频 Provider 时降级行为真实可见；
10. 无权限用户不能访问课堂和 MP4。

后端 Router、Schema 或 Model 发生变化后执行：

```powershell
python scripts/export_implementation_docs.py
python scripts/check_docs.py
```

前端执行：

```powershell
npm run typecheck
npm run build
```

后端执行相关 pytest，并在有数据库变更时执行：

```powershell
python -m alembic upgrade head
```

## 15. 首期不包含的能力

以下能力明确推迟，避免首期失控：

- 将 OpenMAIC 测验替换为 zhixue 测验；
- 将课堂内测验和互动行为回流到诊断、自进化；
- PBL 项目状态与学习路径深度关联；
- 将 OpenMAIC 幻灯片编辑器迁移进 zhixue；
- 原生 PPTX 编辑；
- 白板协作和多人课堂；
- 全站 Stitch 页面联动；
- Docker 正式部署验收。

后续优先顺序为：

```text
课堂互动结果回流
  -> zhixue 测验与诊断关联
  -> PBL 学习路径闭环
  -> 更强图片/视频 Provider
  -> 选择性原生化安全互动场景
```

## 16. 实施约束

1. 不修改或覆盖用户当前 OpenMAIC 本地改造历史；
2. 复制进入 zhixue 时排除 `.git`、`.next`、`node_modules`、生成课堂数据和真实密钥；
3. 不让 OpenMAIC 绕过 Service 层写 zhixue 数据库；
4. 不扩大到无关页面重构；
5. 不因 Docker 问题阻塞本地主链路；
6. 不声称未实现的课堂行为回流、PBL 闭环或完整文生视频能力；
7. 无真实 Provider 时必须明确标记 Mock 或降级模式。
