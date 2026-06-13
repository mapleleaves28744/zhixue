# OpenMAIC 沉浸课堂本地运行指南

> 文档状态：当前运行指南  
> 更新日期：2026-06-13

## 组成与边界

`third_party/openmaic` 是保留 AGPL-3.0 许可证和上游信息的独立课堂引擎。智学工坊后端负责用户权限、课程 RAG、学生画像、任务队列、媒体资产与短期播放签名；OpenMAIC 负责生成和播放沉浸课堂。

## 推荐启动

首次安装 OpenMAIC 依赖：

```powershell
cd third_party/openmaic
pnpm install --frozen-lockfile
```

统一启动：

```powershell
scripts/start_phase31_demo.ps1
```

默认端口：

```text
Frontend  3000
OpenMAIC  3001
Backend   8000
```

启动器会把根 `.env` 中的 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_NAME` 映射为 OpenMAIC 的 Xiaomi MiMo 配置，并在本次进程内生成共享内部密钥。可用 `-SkipOpenMAIC` 跳过课堂引擎。

## 服务器环境变量

服务器应显式配置并让 FastAPI 与 OpenMAIC 使用相同值：

```env
OPENMAIC_ENABLED=true
OPENMAIC_BASE_URL=http://127.0.0.1:3001
OPENMAIC_PUBLIC_BASE_URL=https://your-public-openmaic-origin.example
OPENMAIC_INTERNAL_TOKEN=replace-with-a-long-random-service-token
OPENMAIC_SIGNING_SECRET=replace-with-a-different-long-random-signing-secret
```

OpenMAIC 进程还需 Xiaomi MiMo 配置：

```env
XIAOMI_API_KEY=...
XIAOMI_BASE_URL=...
XIAOMI_MODELS=mimo-v2.5
DEFAULT_MODEL=xiaomi:mimo-v2.5
TTS_XIAOMI_MIMO_API_KEY=...
TTS_XIAOMI_MIMO_BASE_URL=...
ASR_XIAOMI_MIMO_API_KEY=...
ASR_XIAOMI_MIMO_BASE_URL=...
```

## 安全边界

1. `/api/generate-classroom`、任务状态和 manifest 接口要求 `x-openmaic-internal-token`。
2. 学生先通过智学工坊 `media_assets.user_id` 权限校验，再获得短期跳转。
3. 播放令牌绑定课堂 ID 和过期时间，不能用于横向访问其他课堂。
4. OpenMAIC 使用独立来源播放，避免把生成内容直接注入智学工坊主页面。

## 验收

```powershell
scripts/local_check.ps1 -OpenMAIC

cd backend
$env:DEBUG='false'
python -m pytest tests/test_openmaic_client.py tests/test_immersive_classroom.py tests/test_classroom_video_export.py tests/test_supervisor_intents.py -q
```

无真实 MiMo Key 时，智学工坊其他主链路仍可使用 Mock；OpenMAIC 完整真实课堂生成不得用假结果冒充。
