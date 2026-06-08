# 智学工坊 V3 网页端悬浮桌宠落地方案 - Part 4：测试、验收、实施顺序、答辩表达

---

## 20. 测试方案

### 20.1 后端测试

新增文件：

```text
backend/tests/test_agent_active_tasks_api.py
```

示例：

```python
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_list_active_agent_tasks_requires_auth(async_client):
    response = await async_client.get("/api/v1/agent/tasks/active")
    assert response.status_code in {401, 403}


async def test_list_active_agent_tasks_returns_items(auth_client):
    response = await auth_client.get("/api/v1/agent/tasks/active")
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert "items" in payload["data"]
    assert isinstance(payload["data"]["items"], list)
```

如果项目测试里已有 fixture 名称不同，按现有 fixture 替换 `async_client / auth_client`。

---

### 20.2 前端手动测试

#### 测试 1：无后台任务

步骤：

```text
登录
打开 /home
观察右下角桌宠
```

预期：

```text
显示 lulu idle
文案：我会在这里提醒你后台生成进度
点击“开始学习任务”跳到 /assistant
```

#### 测试 2：发起普通 Agent 任务

步骤：

```text
打开 /assistant
输入：帮我生成 BFS 的讲解资料、练习题和三天学习计划
发送
切换到 /dashboard
```

预期：

```text
桌宠仍显示生成中
状态为 focus
显示进度条
点击“查看任务”跳回对应 /assistant?task_id=...
```

#### 测试 3：任务完成

预期：

```text
桌宠状态变 done
文案显示：学习任务完成了，点我查看结果
显示产物数量和引用数量
```

#### 测试 4：任务失败

可以临时断开 LLM Key 或让 mock 抛错。

预期：

```text
桌宠状态变 failed
文案温和提示失败
点击可回到任务卡查看错误
```

#### 测试 5：等待确认

触发：

```text
请应用最新的一条自进化策略
```

预期：

```text
桌宠状态 waiting_confirmation
显示“这个操作需要你确认后才能继续”
点击跳回 assistant
```

---

## 21. V3 实施顺序

### Day 1：最小可用桌宠

完成：

```text
frontend/types/mascot.ts
frontend/lib/zhixue-web-api.ts
frontend/lib/mascot-task-store.ts
frontend/hooks/useAgentTaskPet.ts
frontend/components/GlobalMascot.tsx
frontend/app/layout.tsx
frontend/styles/globals.css
```

验收：

```text
登录后所有页面右下角出现桌宠
无任务时 idle
点击可跳到 /assistant
```

---

### Day 2：接入 Agent 活跃任务

完成：

```text
backend/app/repositories/agent_task_repository.py
backend/app/services/agent_conversation_service.py
backend/app/api/v1/agent.py
frontend/public/stitch-pages/zhixue-static-api.js
frontend/public/stitch-pages/assistant.html
```

验收：

```text
/assistant 创建任务后，桌宠立即变 focus/remind
切到 /dashboard 后继续显示
任务完成后变 done
```

---

### Day 3：接入 IP 四态资源与交互抛光

完成：

```text
scripts/sync_ip_pet_assets.ps1
frontend/public/pets/**
GlobalMascot fallback 测试
移动端适配
```

验收：

```text
/pets 存在时显示四态 pet 图
/pets 不存在时回退 stickers
移动端不遮挡输入框
```

---

### Day 4：接入 V2 多模态任务

完成：

```text
media_jobs active 接口
media job progress broadcast
video/image/courseware 任务进度进入桌宠
```

验收：

```text
生成视频时用户切页，桌宠仍持续提醒
生成完成后点击回到视频资源卡
```

---

## 22. 对 V2 多模态方案的进一步优化建议

### 22.1 ToolRegistry 参数校验必须升级

当前 ToolRegistry 只做简单类型校验。多模态工具参数更复杂，建议用 `jsonschema`：

```python
from jsonschema import Draft202012Validator, ValidationError as JSONSchemaValidationError

def _validate_arguments(self, tool: AgentTool, arguments: dict[str, Any]) -> None:
    schema = tool.input_schema
    try:
        Draft202012Validator(schema).validate(arguments)
    except JSONSchemaValidationError as exc:
        path = ".".join(str(item) for item in exc.absolute_path)
        field = f"参数 {path}" if path else "参数"
        raise ValueError(f"工具 {tool.name} {field} 不合法：{exc.message}") from exc
```

同时在 `backend/requirements.txt` 增加：

```text
jsonschema>=4.23.0
```

---

### 22.2 多模态 Job 要与 Agent Task 强关联

`media_jobs` 建议加：

```python
agent_task_id: UUID | None
conversation_id: UUID | None
tool_call_id: str | None
```

否则桌宠和 Agent 时间线很难知道“哪个视频属于哪个对话任务”。

---

### 22.3 多模态 Provider 不应只适配 Agnes

建议保持抽象：

```text
BaseMultimodalProvider
  MockMultimodalProvider
  AgnesMultimodalProvider
  SeedanceProvider
  XunfeiProvider
  OpenAICompatibleImageProvider
```

`.env` 控制：

```env
MULTIMODAL_PROVIDER=agnes
AGNES_API_KEY=xxx
AGNES_BASE_URL=https://api.agnes-ai.com
AGNES_IMAGE_PATH=/v1/images/generations
AGNES_VIDEO_CREATE_PATH=/v1/videos/generations
AGNES_VIDEO_STATUS_PATH=/v1/videos/{job_id}
```

注意：Agnes 文档如果 endpoint 与示例不同，只改 `.env`，不改业务代码。

---

### 22.4 互动课件要采用 Spec 模型

不要让 LLM 直接写任意 HTML。

推荐结构：

```json
{
  "title": "BFS 广度优先搜索互动课件",
  "goal": "理解队列如何驱动层序遍历",
  "widgets": [
    {
      "type": "graph_traversal",
      "data": {
        "nodes": ["A", "B", "C"],
        "edges": [["A", "B"], ["A", "C"]]
      },
      "question": "下一步访问哪个节点？"
    }
  ],
  "steps": [
    {
      "title": "初始化队列",
      "explanation": "把起点 A 入队。"
    }
  ],
  "citations": []
}
```

服务端模板渲染：

```python
html = render_courseware_template(spec)
```

前端 iframe：

```html
<iframe sandbox="allow-scripts" src="/api/v1/media-assets/{asset_id}/file"></iframe>
```

并设置 CSP：

```text
default-src 'none';
style-src 'unsafe-inline';
script-src 'unsafe-inline';
img-src data:;
```

---

### 22.5 视频生成要有本地兜底

高级文生视频模型不稳定时，建议 fallback：

```text
脚本
-> 分镜
-> SVG / PNG 卡片
-> TTS
-> MoviePy 合成 MP4
```

这样比赛 Demo 不会因为第三方 API 失败而完全不可演示。

---

### 22.6 Review Agent 要升级为多模态 Review

建议新增：

```text
review_multimodal_asset
```

输入：

```json
{
  "asset_type": "video",
  "script": "...",
  "storyboard": [],
  "citations": [],
  "file_meta": {},
  "safety_result": {}
}
```

输出：

```json
{
  "passed": true,
  "risk_level": "low",
  "issues": [],
  "revision_suggestions": [],
  "citation_coverage": 0.86
}
```

---

## 23. 比赛演示脚本建议

### 23.1 演示目标

展示：

```text
对话式画像
多智能体协作
多模态资源生成
网页端桌宠长任务提醒
学习路径与推荐
防幻觉与 Review
```

### 23.2 7 分钟演示脚本

#### 0:00 - 0:40 项目定位

```text
智学工坊不是普通聊天机器人，而是一个能理解学生、构建画像、生成资源、诊断学习、持续推荐的多智能体学习空间。
```

#### 0:40 - 1:30 对话式画像

输入：

```text
我是软件工程大一学生，最近数据结构里的图搜索比较薄弱。
我更喜欢图解、动画和代码案例，每天大概有 45 分钟学习时间。
```

展示：ProfileAgent 更新画像，`/path-profile` 展示画像证据。

#### 1:30 - 2:30 发起个性化学习包

输入：

```text
帮我围绕 BFS 生成一套个性化学习包，包括讲解、思维导图、练习题、互动课件和短视频。
```

展示：`/assistant` Agent 任务卡开始执行，MiMo Supervisor 规划工具，Tool Started / Tool Completed / Observation / Replan。

#### 2:30 - 3:20 切换页面，桌宠提醒

切到 `/dashboard` 或 `/knowledge`，展示右下角网页端桌宠仍显示“我正在帮你生成学习资源”，进度条继续变化，点击可回到任务。

#### 3:20 - 4:30 多模态资源完成

展示讲解文档、思维导图、练习题、互动课件、讲解视频、引用来源、Review Agent 审核结果。

#### 4:30 - 5:30 学习路径与推荐

展示 PlannerAgent 生成三天路径，RecommendAgent 推荐下一步资源。

#### 5:30 - 6:20 安全与防幻觉

展示每个资源带 citations，Review Agent 审查，视频脚本引用课程资料，互动课件 sandbox。

#### 6:20 - 7:00 总结创新

```text
多智能体协同 + 多模态资源生成 + 对话式画像 + 自进化 + 网页端桌宠长任务陪伴。
```

---

## 24. 答辩表述建议

### 24.1 为什么要做网页端桌宠

```text
多模态学习资源生成是长耗时任务，尤其是视频、互动课件和个性化学习包。
传统界面容易让学生长时间停留在一个 loading 页面。
我们设计了网页端全局学习伙伴，它不是装饰，而是一个跨页面任务状态层。
学生可以继续查看 Wiki、练习或开启新对话，桌宠会持续提醒后台 Agent 的生成进度，并在完成后引导学生回到结果页面。
```

### 24.2 为什么不是桌面端

```text
比赛系统是 Web 应用，桌面端会引入 Electron、系统权限、跨平台兼容和安全审核成本。
因此我们把桌宠收敛为 Web 端全局悬浮层，既能解决长任务提醒问题，又不破坏现有部署形态。
```

### 24.3 桌宠和智能体的关系

```text
桌宠不是新的大模型 Agent，也不直接生成内容。
它是 Agent 运行时的可视化陪伴层，订阅 Agent 事件流和多模态任务进度，把后台状态转化为学生能理解的提醒和行动入口。
```

### 24.4 和 IP 形象的关系

```text
我们将 IP 从静态装饰升级为任务状态表达系统。
知知负责知识讲解和 Wiki，露露负责学习路径和提醒，点点负责练习和诊断。
不同任务和状态会触发不同 IP 与表情，从而形成有品牌感、可解释、可陪伴的学习体验。
```

---

## 25. 验收清单

### 25.1 工程验收

```powershell
cd backend
python -m pytest -q --maxfail=1
python -m alembic upgrade head
python scripts/export_implementation_docs.py
python scripts/check_docs.py

cd ..\frontend
npm run typecheck
npm run build
npm audit --audit-level=moderate
```

### 25.2 功能验收

- [ ] 登录后所有主页面出现网页端桌宠
- [ ] 无任务时显示 idle
- [ ] `/assistant` 创建 Agent 任务后桌宠变为 focus/remind
- [ ] 切换到 `/dashboard` 后桌宠仍显示任务
- [ ] 任务完成后桌宠变为 done
- [ ] 任务失败后桌宠变为 failed
- [ ] waiting_confirmation 时桌宠提醒确认
- [ ] 点击桌宠可跳回对应任务
- [ ] 多任务时显示最高优先级任务
- [ ] 可清除已完成任务
- [ ] 移动端不遮挡输入框
- [ ] `/pets` 缺失时可回退 stickers
- [ ] 控制台无报错

### 25.3 比赛演示验收

- [ ] 能演示“生成中切换页面”
- [ ] 能演示“完成后桌宠提醒”
- [ ] 能演示“点击回到任务结果”
- [ ] 能说明 IP 与 Agent 状态映射
- [ ] 能说明为什么不做桌面端
- [ ] 能说明防幻觉和安全审核机制

---

## 26. 最终推荐版本范围

必须做：

```text
1. GlobalMascot
2. /agent/tasks/active
3. assistant.html 广播任务
4. SSE 事件同步状态
5. /pets 或 stickers 回退
6. 完成/失败/确认提醒
```

建议做：

```text
1. media_jobs 接入
2. 多任务展开列表
3. 拖动位置记忆
4. 画像偏好文案
```

暂不做：

```text
1. 桌面端
2. Electron
3. 系统通知权限
4. 任意网页注入式宠物
5. 宠物独立调用 LLM
```

---

## 27. 结论

V3 的核心不是“加一个可爱的图”，而是把 IP 形象升级成 **长任务状态可视化层**。

在当前项目中，它能补上 V2 的最后一块体验短板：

```text
多模态生成很强，但需要时间；
Agent 编排很完整，但用户不一定一直盯着页面；
网页端悬浮桌宠让后台智能体变得可感知、可等待、可返回。
```

这会让智学工坊从“功能完整的学习智能体系统”进一步变成“体验完整的个性化 AI 学习空间”。
