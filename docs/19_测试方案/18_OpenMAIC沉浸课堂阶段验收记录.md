# OpenMAIC 沉浸课堂阶段验收记录

> 验收日期：2026-06-13  
> 验收范围：仓库内 OpenMAIC 模块、智学工坊课堂任务链路、课堂播放隔离、配音字幕 MP4、`/assistant` 产物展示

## 实现结论

已实现从 `/assistant` 一句话路由到个性化 OpenMAIC 沉浸课堂任务，并在课堂完成后创建独立视频导出任务。视频导出读取课堂场景讲解动作，优先复用 OpenMAIC 音频，失败时回退智学工坊 MiMo/Mock TTS，通过 MoviePy 生成带音轨和烧录字幕的 MP4。

## 已执行验收

```text
OpenMAIC 内部鉴权测试：2 passed
OpenMAIC pnpm install --frozen-lockfile：通过
OpenMAIC pnpm build：通过
zhixue 前端 npm run typecheck：通过
zhixue 前端 npm run build：通过
后端 OpenMAIC/课堂/MP4/Agent 聚焦测试：37 passed
后端完整 pytest：265 passed
真实 MoviePy MP4 文件导出：通过，mime=video/mp4，文件大于 1000 bytes
OpenMAIC 生产服务授权冒烟：通过
统一启动脚本冒烟：FastAPI=ok，OpenMAIC=ok
```

授权冒烟验证了：

1. OpenMAIC 健康接口可访问；
2. 内部令牌可写入最小课堂；
3. 未授权课堂 API 返回 401；
4. 绑定课堂 ID 的短期签名可访问对应课堂；
5. 同一签名访问其他课堂被拒绝。

## 当前边界

- 完整真实 MiMo 课堂生成需要服务器正确配置 Xiaomi MiMo Provider，生成耗时与质量需持续回归。
- `/assistant` 同时提供“快速讲解视频”和“沉浸课堂”两个入口：快速讲解视频基于课程检索依据生成中文讲解画面，调用 MiMo TTS 合成配音与烧录字幕；沉浸课堂完成逐场景生成后再创建独立 MP4 导出任务。
- OpenMAIC 单个场景的内容或动作生成受 `OPENMAIC_SCENE_STEP_TIMEOUT_MS` 限制；复杂场景超时后会跳过并继续处理后续场景，避免前端任务永久停留在同一进度。
- MP4 当前根据 OpenMAIC 场景标题和讲解动作生成教学画面、音轨与烧录字幕，不等同于逐帧录制 OpenMAIC 交互界面。
- OpenMAIC 上游许可证、来源和智学工坊改动说明保留在 `third_party/openmaic`。

## 2026-06-13 前端可用性修复

真实运行曾出现 OpenMAIC 在第 5/9 个互动场景生成时长期停留在 56%，最终由上游 MiMo 请求返回 `Headers Timeout`。本次修复：

1. 为课堂单场景内容和动作生成增加超时边界，失败时跳过当前场景并继续；
2. 在 `/assistant` 工具选择器补回“快速讲解视频”，不再让普通视频需求只能走完整沉浸课堂链路；
3. 将卡住的真实课堂任务重新排队，确认任务重新进入 `generating_outlines`；
4. 确认真实 `run_multimodal_video_job` 成功创建视频资产。

## 2026-06-13 文字生成视频与学习资源联动验收

已修复 `/assistant` 文字请求生成快速讲解视频后，前端学习资源区不能稳定感知完成产物的问题：

1. `generate_lesson_video` 文字意图会创建 `video` 学习资源和后台媒体任务；
2. 快速视频不再使用无音轨、中文字体不完整的旧占位渲染，统一输出中文画面、MiMo 配音、AAC 音轨和烧录字幕；
3. 视频完成事件同时返回 `resource_id`、`asset_id` 和 `artifact_refs`，前端收到事件后刷新学习资源区；
4. 学习资源记录完成后显示“讲解视频已生成，可在学习资源区直接播放”，资源详情返回 `preview_mode=video` 和媒体播放地址；
5. 真实 BFS 视频资产 `242539f8-83c5-40a5-835c-e53e36a9f528` 已绑定资源 `9963bda0-c85b-4afc-9267-5fc5a205bb82`。

真实文件验收：

```text
视频编码：H264，1280×720
音频编码：AAC，双声道，44100 Hz
时长：155.84 秒
MiMo 配音：7/7 段成功，audio_degraded=false
资源预览：preview_mode=video
前端 npm run build：通过
后端聚焦测试：37 passed
```

## 2026-06-13 沉浸课堂生成速度优化

在不改变课堂场景数量、分镜结构、画面切换顺序、讲解段落和 MoviePy 拼接方式的前提下，完成以下等待时间优化：

1. 不同课堂场景以保守并发度 `2` 生成；每个场景内部仍严格保持“内容生成 → 动作生成”的顺序，最终按原始大纲顺序写入课堂；
2. OpenMAIC 课堂 TTS 以保守并发度 `2` 生成，每条 speech action 仍保留独立音频和原有顺序；
3. MP4 导出优先直接复用仓库内 OpenMAIC 已生成音频，不再绕 HTTP 下载或重复调用 MiMo TTS；
4. 保留原有 `8 FPS`、H264、AAC、720p、40 段分镜、原顺序和原时间线；MoviePy 对同尺寸分镜使用 `chain` 执行层拼接，跳过无意义的逐帧画布重合成，未采用静态 FFmpeg 替代或合并分镜。

真实 BFS 课堂阶段分析：

```text
正常重跑场景生成（10 场景，原串行）：约 16 分 40 秒
OpenMAIC TTS（原串行）：约 4 分 28 秒
优化后建议并发度：场景 2，TTS 2
已有课堂导出音频复用：40/40 段命中本地原始音频
40 段音频准备耗时：约 35.9 秒
同一 40 段、693.44 秒课堂视频优化后完整导出：约 2 分 23 秒
导出结果：H264 1280×720 + AAC 双声道 44100 Hz，40/40 段本地原音频复用
```

并发度保持低值是为了避免 Xiaomi MiMo Token Plan 的单 Key 并发配额触发 429 或超时；需要提高时应先确认上游配额。
