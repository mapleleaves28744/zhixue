# change_2 — 工具拓展与差距弥补推进方案

> 文档状态：**实施规划**
> 创建日期：2026-06-07
> 最近修订：2026-06-08
> 目标：补齐赛题要求与当前实现之间的差距，扩展 Agent 工具集

> 修订原则：本文仍保留原 T1-T6 / S1-S4 结构，不推倒重写；所有实现契约以 `docs/当前实现基线.md`、当前代码、OpenAPI、SQLAlchemy Model 和真实验收记录为准。若本文代码片段与当前实现冲突，以本次修订后的“落地契约 / 验收 Gate”为准。

---

## 一、当前状态总结

### 已有 12 个 Agent 工具

| # | 工具名 | 功能 |
|---|--------|------|
| 1 | `search_course_knowledge` | 混合 RAG 检索 |
| 2 | `answer_course_question` | AI 答疑（含引用） |
| 3 | `generate_learning_path` | 学习路径生成 |
| 4 | `generate_explanation` | 讲解文档/总结/案例/闪卡/复习 |
| 5 | `generate_quiz` | 练习题生成 |
| 6 | `analyze_learning_diagnosis` | 学习诊断 |
| 7 | `refresh_recommendations` | 资源推荐刷新 |
| 8 | `update_profile_from_dialogue` | 对话式画像更新 |
| 9 | `rebuild_profile` | 画像重建 |
| 10 | `reflect_learning_memory` | 长期记忆反思 |
| 11 | `review_artifacts` | 内容审查 |
| 12 | `apply_evolution_strategy` | 自进化策略应用 |

### 赛题核心要求 vs 差距

| 赛题要求 | 状态 | 差距 |
|---------|------|------|
| ① 对话式画像 ≥6 维度 | ✅ 已覆盖 | 需验证对话抽取 prompt 是否覆盖全部维度 |
| ② 多智能体协同 ≥5 类资源 | ⚠️ 5 类但纯文本 | 缺思维导图、图解、多题型 |
| ③ 个性化学习路径 + 资源推送 | ⚠️ 被动查询 | 缺主动推送机制 |
| ④ 智能辅导（加分） | ✅ 已有 | 缺多模态答疑（图解、语音） |
| ⑤ 学习效果评估（加分） | ⚠️ 有诊断 | 缺实时行为追踪、策略自动调整 |
| 防幻觉 + 内容安全 | ⚠️ 仅风险评级 | 缺事实校验、敏感词拦截 |
| 流式输出 | ✅ Agent SSE 已接 | 长耗时多模态工具需复用现有事件并补更细粒度进度 |
| 外部 AI 工具 | ⚠️ MiMo 已用于文本 Agent | 语音/多模态工具需接入 MiMo Token Plan 真实模型，失败时 Mock 兜底 |

### 当前实现约束（本轮新增）

1. 当前学生端不是 React 业务组件化应用，主要交互在 `frontend/public/stitch-pages/*.html` 和 `frontend/public/stitch-pages/zhixue-static-api.js`；除非单独确认，不新建一套 React 学生端页面。
2. Agent 工具统一注册在 `backend/app/agent_runtime/service_tools.py`，执行链路已经通过 `LearningAgentGraph` 产生 `tool_started`、`tool_completed`、`observation`、`reviewed`、`completed` 等事件，并由 `/api/v1/agent/tasks/{task_id}/events` SSE 推给 `/assistant`。
3. 资源表 `generated_resources` 当前没有 `format`、`metadata` 字段；第一版 Mermaid 类资源优先把 Mermaid 文本存入 `content`，来源与参数放入 `citations` / `personalized_reason`，避免不必要 migration。
4. 真实语音模型优先使用小米 MiMo Token Plan：`mimo-v2.5-asr`、`mimo-v2.5-tts`、`mimo-v2.5-tts-voiceclone`、`mimo-v2.5-tts-voicedesign`。当前 API 已可直接调用，因此比赛演示和本地验收应尽量跑真实模型；只有缺少配置、接口超时或调用失败时才回退 Mock，并在工具输出中明确 `fallback_used=true`、`failed_provider=xiaomi_mimo_audio` 和失败原因摘要。
5. 数据库结构若确需变化，必须同步 Model、Alembic migration、Schema，并执行 `python scripts/export_implementation_docs.py`；文档变更后执行 `python scripts/check_docs.py`。

---

## 二、工具拓展清单（共 5 个新工具 + 1 个扩展）

### T1: `parse_uploaded_document` — 文档解析工具

**优先级**：P0（立即做，但不是 30 分钟任务）
**工时**：1-1.5 小时
**对应缺口**：Agent 无法主动触发文档解析

#### 功能定义

```
工具名: parse_uploaded_document
描述: 解析已上传的课程资料（PDF/DOCX/TXT/MD），自动切片和向量化，供 RAG 检索使用。
输入:
  - material_id (string, required): 课程资料 ID
风险等级: low
writes_db: true
```

#### 落地契约

当前真实能力：

- 上传资料由 `MaterialService` 管理，允许类型见 `backend/app/services/material_service.py` 中的 `ALLOWED_MATERIAL_TYPES = {"pdf", "docx", "md", "txt"}`。
- 解析入口为 `MaterialService.parse_material(material_id, current_user)`，内部调用 `MaterialParseService.parse_material()` 并自动触发 `ChunkService.chunk_material()`。
- 向量化入口为 `EmbeddingService.generate_embeddings(material_id)`。
- `ToolContext` 只包含 `task_id`、`conversation_id`、`tool_call_id`、`user_id`、`course_id`，没有当前资料 ID，因此 `material_id` 必须显式传入；Supervisor 不应凭空从上下文补 ID。

#### 实现方案

在 `backend/app/agent_runtime/service_tools.py` 中新增工具，包装现有 service：

```python
async def parse_document(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
    from app.services.embedding_service import EmbeddingService
    from app.services.material_service import MaterialService

    material_id = UUID(str(arguments["material_id"]))
    parse_result = await MaterialService(db).parse_material(
        material_id=material_id,
        current_user=current_user,
    )
    embedded_count = await EmbeddingService(db).generate_embeddings(material_id)

    return ToolExecutionResult(
        output={
            "material_id": str(material_id),
            "file_name": parse_result.file_name,
            "text_length": parse_result.text_length,
            "parse_status": parse_result.parse_status,
            "embedded_count": embedded_count,
        },
        evidence=[
            f"已解析 {parse_result.file_name}，提取 {parse_result.text_length} 字符",
            f"已生成 {embedded_count} 个向量切片",
        ],
        artifact_refs=[
            {
                "type": "material",
                "id": str(material_id),
                "title": parse_result.file_name,
            }
        ],
    )
```

#### 注册信息

```python
_register(
    registry,
    name="parse_uploaded_document",
    description="解析已上传的课程资料（PDF/DOCX/PPT/TXT/MD），自动切片和向量化，供 RAG 检索使用。",
    agent_name="KnowledgeAgent",
    properties={"material_id": {"type": "string", "description": "课程资料 UUID"}},
    required=["material_id"],
    handler=parse_document,
    writes_db=True,
)
```

#### Supervisor 关键词触发

在 `supervisor.py` 的 `_required_tools()` 中添加：

```python
("parse_uploaded_document", ("解析资料", "解析文档", "处理上传", "解析这份")),
```

在 `_safe_arguments()` 中添加：

```python
"parse_uploaded_document": {},  # 不自动补 material_id；缺参时让工具失败并产生 observation，Supervisor 再追问
```

#### 验收 Gate

1. 单元测试：新增 `backend/tests/test_agent_runtime.py` 或独立测试，验证工具 schema 要求 `material_id`，且缺参时不会被 `_safe_arguments()` 伪造。
2. 集成测试：上传一份小型 `.txt` 或 `.md` 资料后，通过 Agent 工具调用解析，验证 `parse_status=success`、`embedded_count > 0`、`artifact_refs[0].type == "material"`。
3. 前端联动：`/assistant` 时间线能看到 `tool_started → tool_completed → observation`；`/knowledge` 资料列表能看到解析状态变化。
4. 文档同步：若只新增 Agent 工具，不改 Router/Schema/Model，则无需执行 `export_implementation_docs.py`；完成后仍需更新本方案执行状态。

---

### T2: `generate_mindmap` — 思维导图生成

**优先级**：P0（赛题明确要求）
**工时**：1-2 小时
**对应缺口**：赛题要求"知识点思维导图"

#### 功能定义

```
工具名: generate_mindmap
描述: 围绕课程知识点生成 Mermaid 思维导图，可视化知识结构关系。
输入:
  - topic (string, required): 知识主题
  - scope (string, optional): 范围，默认 "course"，可选 "chapter" / "custom"
  - depth (integer, optional): 层级深度，默认 3，范围 2-5
风险等级: low
writes_db: true
```

#### 实现方案

**新建文件**：`backend/app/services/mindmap_service.py`

同时修改：

- `backend/app/schemas/resource.py`：`VALID_RESOURCE_TYPES` 增加 `mindmap`，`RESOURCE_TYPE_ALIASES` 增加中文别名。
- `backend/app/services/resource_service.py`：`_normalize_resource_type()` 错误提示和 `_default_title()` 增加 `mindmap`。
- `backend/app/agent_runtime/service_tools.py`：注册 `generate_mindmap`。
- `backend/app/agent_runtime/supervisor.py`：增加关键词触发和安全参数补全。

第一版不新增 `generated_resources.format` 或 `generated_resources.metadata` 字段，避免不必要 migration。Mermaid 代码直接写入 `GeneratedResource.content`；来源 chunk、topic、scope、depth 放入 `citations` 和 `personalized_reason`。

```python
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.provider import get_llm_provider
from app.llm.schemas import ChatMessage
from app.models.user import User
from app.repositories.resource_repository import ResourceRepository
from app.services.knowledge_search_service import KnowledgeSearchService


class MindmapService:
    """基于课程检索上下文生成 Mermaid mindmap 学习资源。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def generate(
        self,
        *,
        current_user: User,
        course_id: UUID,
        topic: str,
        scope: str = "course",
        depth: int = 3,
    ) -> dict[str, Any]:
        depth = max(2, min(5, int(depth)))
        knowledge_items = await KnowledgeSearchService(self.db).search(
            current_user=current_user,
            course_id=course_id,
            query=topic,
            top_k=15,
        )

        prompt = self._build_mindmap_prompt(
            topic=topic,
            knowledge_items=knowledge_items,
            depth=depth,
        )

        llm = get_llm_provider(
            db=self.db,
            user_id=current_user.id,
            course_id=course_id,
        )
        response = await llm.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=0.5,
            max_tokens=4096,
        )

        mermaid_code = self._extract_mermaid(response.content)
        citations = self._build_citations(knowledge_items, topic=topic, scope=scope, depth=depth)

        resource = await ResourceRepository(self.db).create(
            user_id=current_user.id,
            course_id=course_id,
            knowledge_id=None,
            wiki_page_id=None,
            resource_type="mindmap",
            title=f"{topic} 知识思维导图",
            content=mermaid_code,
            citations=citations,
            personalized_reason=f"基于课程检索片段生成，范围={scope}，深度={depth}",
            model_name=response.model,
            prompt_version_id=None,
        )
        await self.db.commit()
        await self.db.refresh(resource)

        return {
            "resource_id": str(resource.id),
            "title": resource.title,
            "mermaid_code": mermaid_code,
            "content": mermaid_code,
            "citations": citations,
            "topic": topic,
        }

    def _build_mindmap_prompt(self, topic: str, knowledge_items: list[dict[str, Any]], depth: int) -> str:
        context = "\n".join([
            f"- {item.get('source_title', '')}: {item.get('content', '')[:200]}"
            for item in knowledge_items[:10]
        ])
        return (
            f"请围绕「{topic}」生成一个 Mermaid mindmap 思维导图。\n\n"
            f"参考知识片段：\n{context}\n\n"
            f"要求：\n"
            f"1. 使用 Mermaid mindmap 语法\n"
            f"2. 最大深度 {depth} 层\n"
            f"3. 中心节点为「{topic}」\n"
            f"4. 每个子节点包含简要说明（10字以内）\n"
            f"5. 节点间体现知识依赖和逻辑关系\n"
            f"6. 只输出 Mermaid 代码，不要其他解释\n\n"
            f"格式示例：\n"
            f"mindmap\n"
            f"  root({topic})\n"
            f"    子主题A\n"
            f"      细节点1\n"
            f"      细节点2\n"
            f"    子主题B"
        )

    def _extract_mermaid(self, content: str) -> str:
        match = re.search(r"```mermaid\s*\n(.*?)```", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        if "mindmap" in content:
            start = content.index("mindmap")
            return content[start:].strip()
        cleaned = content.strip()
        if not cleaned.startswith("mindmap"):
            return f"mindmap\n  root({cleaned[:40] or '知识结构'})"
        return cleaned

    def _build_citations(
        self,
        knowledge_items: list[dict[str, Any]],
        *,
        topic: str,
        scope: str,
        depth: int,
    ) -> list[dict[str, Any]]:
        citations = []
        for item in knowledge_items[:8]:
            citations.append(
                {
                    "source_type": "document",
                    "title": item.get("source_title") or "课程资料",
                    "source_id": item.get("material_id"),
                    "chunk_id": item.get("chunk_id"),
                    "page_no": item.get("page_no"),
                    "score": item.get("score"),
                    "quote": str(item.get("content") or "")[:240],
                }
            )
        citations.append(
            {
                "source_type": "generation_config",
                "title": "mindmap_generation",
                "extra": {"topic": topic, "scope": scope, "depth": depth},
            }
        )
        return citations
```

#### 注册信息

```python
_register(
    registry,
    name="generate_mindmap",
    description="围绕课程知识点生成 Mermaid 思维导图，可视化知识结构关系。",
    agent_name="KnowledgeAgent",
    properties={
        "topic": {"type": "string", "description": "知识主题"},
        "scope": {"type": "string", "enum": ["course", "chapter", "custom"]},
        "depth": {"type": "integer", "minimum": 2, "maximum": 5},
    },
    required=["topic"],
    handler=generate_mindmap_handler,
    writes_db=True,
)
```

工具 handler：

```python
async def generate_mindmap_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
    from app.services.mindmap_service import MindmapService

    topic = str(arguments.get("topic") or "").strip()
    if not topic:
        topic = "数据结构知识结构"
    result = await MindmapService(db).generate(
        current_user=current_user,
        course_id=context.course_id,
        topic=topic,
        scope=str(arguments.get("scope") or "course"),
        depth=int(arguments.get("depth") or 3),
    )
    return ToolExecutionResult(
        output=result,
        evidence=result.get("citations") or [],
        citations=result.get("citations") or [],
        artifact_refs=[
            {
                "type": "resource",
                "subtype": "mindmap",
                "id": result["resource_id"],
                "title": result["title"],
            }
        ],
    )
```

#### 前端展示

在 `/knowledge` 页面的 Wiki 详情区增加"查看思维导图"按钮，使用 Mermaid.js 渲染：

```html
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.esm.min.mjs';
  mermaid.initialize({ startOnLoad: true, theme: 'default' });
</script>
<pre class="mermaid">{mermaid_code}</pre>
```

注意：当前前端主形态是 Stitch 静态页，优先在 `frontend/public/stitch-pages/knowledge.html` 或 `/assistant` 的 artifact 卡片中渲染，不新建 React 页面。若要加载 CDN Mermaid，应在比赛部署文档中说明外网依赖；离线演示建议把 Mermaid 打包到本地静态资源或使用文本预览兜底。

#### Supervisor 关键词触发

```python
("generate_mindmap", ("思维导图", "知识图谱", "知识结构", "梳理一下脉络", "整体框架")),
```

在 `_safe_arguments()` 中为缺参补默认主题：

```python
"generate_mindmap": {"topic": goal, "scope": "course", "depth": 3},
```

#### 验收 Gate

1. 后端测试：调用 `MindmapService.generate()`，断言返回 `mindmap` 开头内容、写入 `generated_resources.resource_type == "mindmap"`、`citations` 非空。
2. Agent 测试：Supervisor 遇到“生成思维导图/知识结构”目标时会选择 `generate_mindmap`。
3. 前端测试：`/assistant` 时间线中 artifact_refs 显示为资源卡；如 `/knowledge` 接入按钮，Mermaid 渲染失败时必须显示原始代码而非空白。
4. 文档同步：若只扩展资源类型常量和 Agent 工具，不改 API 路由或数据库模型，不需要 migration；若新增 API 响应字段，再执行 `export_implementation_docs.py`。

---

### T3: `transcribe_audio` — 语音转文字

**优先级**：P1（真实 MiMo 优先，Mock 仅兜底）
**工时**：2-3 小时
**对应缺口**：多模态语音输入、语音提问演示

#### 功能定义

```
工具名: transcribe_audio
描述: 将音频文件转换为文字，支持语音提问、语音笔记等场景。
输入:
  - audio_base64 (string, required): Base64 编码的音频数据
  - filename (string, optional): 文件名，用于推断格式
  - language (string, optional): 语言代码，默认 "zh"
风险等级: low
writes_db: false
timeout_seconds: 60
```

#### 落地契约

1. 语音能力不直接散落在业务代码中，必须通过 `backend/app/llm/audio_provider.py` 的统一抽象。
2. Provider 至少包含：
   - `MiMoTokenPlanAudioProvider`：真实调用小米 MiMo Token Plan ASR/TTS；
   - `MockAudioProvider`：仅在缺配置或真实调用失败时返回可演示文本和短音频占位信息；
   - `FallbackAudioProvider`：先调用 `MiMoTokenPlanAudioProvider`，失败后调用 `MockAudioProvider`，并返回 fallback 元数据。
3. Agent 工具本身只调用 Provider，不直接写 `httpx.post()`。
4. 输入 `audio_base64` 不能写入日志全文；Agent 事件和 `llm_call_logs` 只能记录文件名、字节数、模型、耗时、状态等脱敏信息。
5. 当前第一版只实现工具层和 `/assistant` 可演示入口；不要求把整站输入框改造成完整语音聊天组件。

#### 实现方案

**新建文件**：`backend/app/llm/audio_provider.py`

```python
"""Audio provider abstraction for ASR / TTS."""

from __future__ import annotations

import base64
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ASRResult:
    text: str
    duration_ms: int = 0
    language: str = "zh"
    model: str = "mock-asr"
    provider: str = "mock_audio"
    raw: dict[str, object] | None = None


@dataclass
class TTSResult:
    audio_base64: str
    duration_ms: int = 0
    format: str = "wav"
    model: str = "mock-tts"
    provider: str = "mock_audio"
    raw: dict[str, object] | None = None


class BaseAudioProvider(ABC):
    provider_name = "base_audio"

    @abstractmethod
    async def transcribe(
        self,
        audio_base64: str,
        *,
        filename: str = "audio.wav",
        language: str = "zh",
    ) -> ASRResult:
        ...

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "wav",
        model: str | None = None,
    ) -> TTSResult:
        ...


class MockAudioProvider(BaseAudioProvider):
    provider_name = "mock_audio"

    async def transcribe(
        self,
        audio_base64: str,
        *,
        filename: str = "audio.wav",
        language: str = "zh",
    ) -> ASRResult:
        byte_count = len(base64.b64decode(audio_base64 + "===")) if audio_base64 else 0
        return ASRResult(
            text=f"这是 Mock 语音识别结果：学生通过 {filename} 提问，请围绕数据结构课程进行讲解。",
            duration_ms=max(1, byte_count // 32),
            language=language,
            model="mock-asr",
            provider=self.provider_name,
        )

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "wav",
        model: str | None = None,
    ) -> TTSResult:
        # 第一版 Mock 不生成真实音频，只返回可展示占位内容，避免无 Key 时演示中断。
        placeholder = f"MOCK_AUDIO:{response_format}:{speed}:{text[:120]}"
        return TTSResult(
            audio_base64=base64.b64encode(placeholder.encode("utf-8")).decode("utf-8"),
            duration_ms=max(1, len(text) * 20),
            format=response_format,
            model=model or "mock-tts",
            provider=self.provider_name,
        )


class FallbackAudioProvider(BaseAudioProvider):
    provider_name = "fallback_audio"

    def __init__(self, primary: BaseAudioProvider, fallback: BaseAudioProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    async def transcribe(
        self,
        audio_base64: str,
        *,
        filename: str = "audio.wav",
        language: str = "zh",
    ) -> ASRResult:
        try:
            result = await self.primary.transcribe(
                audio_base64,
                filename=filename,
                language=language,
            )
            result.raw = {"fallback_used": False}
            return result
        except Exception as exc:
            logger.warning("MiMo ASR failed, falling back to mock: %s", exc)
            result = await self.fallback.transcribe(
                audio_base64,
                filename=filename,
                language=language,
            )
            result.raw = {
                "fallback_used": True,
                "failed_provider": self.primary.provider_name,
                "fallback_reason": str(exc)[:300],
            }
            return result

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "wav",
        model: str | None = None,
    ) -> TTSResult:
        try:
            result = await self.primary.synthesize(
                text,
                voice=voice,
                speed=speed,
                response_format=response_format,
                model=model,
            )
            result.raw = {"fallback_used": False}
            return result
        except Exception as exc:
            logger.warning("MiMo TTS failed, falling back to mock: %s", exc)
            result = await self.fallback.synthesize(
                text,
                voice=voice,
                speed=speed,
                response_format=response_format,
                model=model,
            )
            result.raw = {
                "fallback_used": True,
                "failed_provider": self.primary.provider_name,
                "fallback_reason": str(exc)[:300],
            }
            return result


MIMO_ASR_MODEL = "mimo-v2.5-asr"
MIMO_TTS_MODEL = "mimo-v2.5-tts"
MIMO_TTS_VOICECLONE_MODEL = "mimo-v2.5-tts-voiceclone"
MIMO_TTS_VOICEDESIGN_MODEL = "mimo-v2.5-tts-voicedesign"


class MiMoTokenPlanAudioProvider(BaseAudioProvider):
    """Xiaomi MiMo Token Plan audio provider for ASR/TTS endpoints."""

    provider_name = "xiaomi_mimo_audio"

    def __init__(self) -> None:
        self._api_key = settings.llm_api_key
        self._base_url = (settings.llm_base_url or "").rstrip("/")
        self._asr_model = MIMO_ASR_MODEL

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def transcribe(
        self,
        audio_base64: str,
        *,
        filename: str = "audio.wav",
        language: str = "zh",
    ) -> ASRResult:
        audio_bytes = base64.b64decode(audio_base64)
        files = {"file": (filename, audio_bytes, "audio/wav")}
        data = {
            "model": self._asr_model,
            "language": language,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                files=files,
                data=data,
            )
            resp.raise_for_status()
            result = resp.json()

        return ASRResult(
            text=result.get("text", ""),
            duration_ms=result.get("duration", 0),
            language=result.get("language", language),
            model=self._asr_model,
            provider=self.provider_name,
        )

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "wav",
        model: str | None = None,
    ) -> TTSResult:
        model = model or MIMO_TTS_MODEL
        if model not in {
            MIMO_TTS_MODEL,
            MIMO_TTS_VOICECLONE_MODEL,
            MIMO_TTS_VOICEDESIGN_MODEL,
        }:
            model = MIMO_TTS_MODEL
        payload = {
            "model": model,
            "input": text,
            "response_format": response_format,
            "speed": speed,
        }
        if voice:
            payload["voice"] = voice

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/audio/speech",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            audio_bytes = resp.content

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return TTSResult(
            audio_base64=audio_b64,
            format=response_format,
            model=model,
            provider=self.provider_name,
        )


def build_audio_provider() -> BaseAudioProvider:
    if settings.llm_api_key and settings.llm_base_url:
        return FallbackAudioProvider(
            primary=MiMoTokenPlanAudioProvider(),
            fallback=MockAudioProvider(),
        )
    return MockAudioProvider()
```

#### 工具注册（service_tools.py）

```python
async def transcribe_audio(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
    import base64
    from app.llm.audio_provider import build_audio_provider

    audio_base64 = str(arguments["audio_base64"])
    byte_count = len(base64.b64decode(audio_base64 + "===")) if audio_base64 else 0
    provider = build_audio_provider()
    result = await provider.transcribe(
        audio_base64=audio_base64,
        filename=str(arguments.get("filename") or "audio.wav"),
        language=str(arguments.get("language") or "zh"),
    )
    return ToolExecutionResult(
        output={
            "text": result.text,
            "duration_ms": result.duration_ms,
            "language": result.language,
            "provider": result.provider,
            "model": result.model,
            "audio_bytes": byte_count,
            "fallback_used": bool((result.raw or {}).get("fallback_used")),
            "failed_provider": (result.raw or {}).get("failed_provider"),
        },
        evidence=[
            f"语音识别完成，provider={result.provider}，模型={result.model}",
            f"输入音频 {byte_count} bytes，识别文本 {len(result.text)} 字",
        ],
    )
```

```python
_register(
    registry,
    name="transcribe_audio",
    description="将音频文件转换为文字，支持语音提问、语音笔记等场景。",
    agent_name="TutorAgent",
    properties={
        "audio_base64": {"type": "string", "description": "Base64 编码的音频数据"},
        "filename": {"type": "string", "description": "文件名（用于推断格式）"},
        "language": {"type": "string", "description": "语言代码，默认 zh"},
    },
    required=["audio_base64"],
    handler=transcribe_audio,
)
```

#### 前端接入

第一版优先在 `/assistant` 增加轻量语音入口：

1. 在 `frontend/public/stitch-pages/assistant.html` 的输入区增加录音/上传音频按钮。
2. 使用浏览器 `MediaRecorder` 或文件上传转 base64。
3. 调用统一 Agent 消息时，目标文本中明确包含“请先调用 transcribe_audio 识别这段音频，再回答问题”，或单独调用工具后把识别文本填入输入框。
4. 无浏览器录音权限时，保留“上传音频文件”兜底。

#### 验收 Gate

1. 配置 `LLM_API_KEY` 和 `LLM_BASE_URL` 时，`transcribe_audio` 优先调用 `provider=xiaomi_mimo_audio`、`model=mimo-v2.5-asr`，且成功时 `fallback_used=false`。
2. 真实 MiMo 调用失败时才返回 `provider=mock_audio`，并带 `fallback_used=true`、`failed_provider=xiaomi_mimo_audio`、`fallback_reason` 摘要；Agent 任务不失败。
3. 无真实配置时可 Mock 演示，但验收记录必须标注这是 Mock fallback，不得冒充真实语音模型效果。
4. 识别结果不保存原始 base64 到事件或日志。
5. `/assistant` 至少能完成“上传/录音 → 识别文本 → 基于文本答疑”的演示。
6. 失败时前端显示“语音识别失败，可改用文字输入”，不得白屏。

---

### T4: `synthesize_speech` — 文字转语音

**优先级**：P1（与 T3 同批）
**工时**：1-2 小时
**对应缺口**：多模态语音输出

#### 功能定义

```
工具名: synthesize_speech
描述: 将文字转换为语音，用于讲解朗读、错题语音反馈等场景。
输入:
  - text (string, required): 要转换的文字
  - model_type (string, optional): tts / voiceclone / voicedesign，默认 tts
  - voice (string, optional): 音色，默认由 Provider 决定
  - speed (number, optional): 语速，0.5-2.0，默认 1.0
  - response_format (string, optional): wav / mp3，默认 wav
风险等级: low
writes_db: false
timeout_seconds: 120
```

#### 实现方案

```python
async def synthesize_speech_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
    from app.llm.audio_provider import (
        MIMO_TTS_MODEL,
        MIMO_TTS_VOICECLONE_MODEL,
        MIMO_TTS_VOICEDESIGN_MODEL,
        build_audio_provider,
    )

    text = str(arguments["text"]).strip()
    model_type = str(arguments.get("model_type") or "tts")
    model_map = {
        "tts": MIMO_TTS_MODEL,
        "voiceclone": MIMO_TTS_VOICECLONE_MODEL,
        "voicedesign": MIMO_TTS_VOICEDESIGN_MODEL,
    }
    provider = build_audio_provider()
    result = await provider.synthesize(
        text=text,
        voice=str(arguments.get("voice") or "") or None,
        speed=float(arguments.get("speed") or 1.0),
        response_format=str(arguments.get("response_format") or "wav"),
        model=model_map.get(model_type, MIMO_TTS_MODEL),
    )
    return ToolExecutionResult(
        output={
            "audio_base64": result.audio_base64,
            "format": result.format,
            "model": result.model,
            "provider": result.provider,
            "duration_ms": result.duration_ms,
            "text_length": len(text),
            "fallback_used": bool((result.raw or {}).get("fallback_used")),
            "failed_provider": (result.raw or {}).get("failed_provider"),
        },
        evidence=[
            f"语音合成完成，provider={result.provider}，模型={result.model}",
            f"输出格式 {result.format}，文本 {len(text)} 字",
        ],
    )
```

```python
_register(
    registry,
    name="synthesize_speech",
    description="将文字转换为语音，用于讲解朗读、错题语音反馈等场景。",
    agent_name="TutorAgent",
    properties={
        "text": {"type": "string", "description": "要转换的文字"},
        "model_type": {"type": "string", "enum": ["tts", "voiceclone", "voicedesign"]},
        "voice": {"type": "string", "description": "音色，可由具体 Provider 解释"},
        "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0},
        "response_format": {"type": "string", "enum": ["wav", "mp3"]},
    },
    required=["text"],
    handler=synthesize_speech_handler,
)
```

#### 前端接入

1. 在 `/assistant` 的最终回答卡片中增加“朗读”按钮。
2. 点击后调用 Agent 工具或后端工具包装接口生成音频；优先展示真实 `provider=xiaomi_mimo_audio` 输出。若返回 `provider=mock_audio` 且 `fallback_used=true`，前端显示“真实语音接口暂不可用，已使用 Mock 兜底”。
3. 真实音频返回后使用 `<audio controls>` 展示，不把 base64 原文长期写入页面历史。

#### 验收 Gate

1. 配置真实 MiMo 时，默认 `model_type=tts` 调用 `mimo-v2.5-tts`，成功时 `provider=xiaomi_mimo_audio` 且 `fallback_used=false`。
2. `model_type=voiceclone` 调用 `mimo-v2.5-tts-voiceclone`；`model_type=voicedesign` 调用 `mimo-v2.5-tts-voicedesign`。
3. 真实模式下如果接口超时或失败，工具回退 Mock，返回 `provider=mock_audio`、`fallback_used=true`、`failed_provider=xiaomi_mimo_audio`，Supervisor 可继续用文字回答。
4. 前端点击朗读不影响原文字答疑和引用展示。

---

### T5: 扩展 `generate_quiz` — 多题型支持

**优先级**：P0（赛题明确要求）
**工时**：2-4 小时
**对应缺口**：当前 Schema 已支持多题型，但 Prompt、fallback、前端展示和测试覆盖仍偏单选题

#### 当前状态

- `VALID_QUESTION_TYPES` 已定义 6 种：`single_choice, multiple_choice, judge, short_answer, fill_blank, coding`（schemas/quiz.py:11-18）
- `supervisor.py` 已有中文别名映射（:286-308）
- `QuizService._is_correct()` 已对 `single_choice / multiple_choice / judge` 做精确匹配，对其他题型做基础包含式判断
- `QuizAgent._fallback_question()` 对非选择题已有简答式兜底，但没有区分判断、填空、编程
- `PromptService` 的 `quiz.generate` 模板示例仍固定为 `single_choice`，容易诱导 LLM 只生成单选题
- `/practice` 页面需要确认是否能展示非选择题输入框、判断题、填空题和编程题文本

#### 需要改动

**文件 1：`backend/app/services/prompt_service.py`**

修改 `QuizAgent / quiz.generate` 内置 Prompt，明确 6 种题型的 JSON 契约。示例不再只放 `single_choice`，而是说明按 `question_types` 输出：

```python
"题型说明：\n"
"- single_choice: options 为 A/B/C/D 对象，standard_answer 为单个选项字母。\n"
"- multiple_choice: options 为 A/B/C/D 对象，standard_answer 为多个选项字母，如 A,C。\n"
"- judge: options 为 {\"正确\":\"正确\", \"错误\":\"错误\"} 或空对象，standard_answer 为 正确/错误。\n"
"- fill_blank: question_text 必须包含 ____，options 为空对象或空数组，standard_answer 可用 | 分隔同义答案。\n"
"- short_answer: options 为空对象或空数组，standard_answer 为 100-300 字参考答案。\n"
"- coding: question_text 包含输入输出要求，analysis 给出参考代码或伪代码，standard_answer 写核心思路。\n"
```

**文件 2：`backend/app/agents/quiz_agent.py`**

细化 `_fallback_question()`，不同题型给不同兜底，避免 LLM 返回空内容时全变简答题：

```python
if question_type == "judge":
    return {
        "question_type": "judge",
        "difficulty": difficulty,
        "question_text": f"第 {index + 1} 题：学习「{knowledge_name}」时，只背定义而不理解操作过程也能稳定迁移应用。判断正误。",
        "options": {"正确": "正确", "错误": "错误"},
        "standard_answer": "错误",
        "analysis": "数据结构学习需要把定义、操作过程、复杂度和应用场景联动理解。",
        "error_tags": ["概念理解偏差"],
        "created_by": "system",
    }
```

**文件 3：`backend/app/services/quiz_service.py`**

保持现有判分基本逻辑，但补两个稳定性点：

```python
def _normalize_question_item(...):
    ...
    if normalized_type == "judge" and not item.get("options"):
        options = {"正确": "正确", "错误": "错误"}
    elif normalized_type in {"fill_blank", "short_answer", "coding"}:
        options = item.get("options") or []
    else:
        options = item.get("options") or []
```

填空题答案归一化时允许 `|` 分隔同义答案：

```python
if question.question_type == "fill_blank":
    standards = [self._normalize_answer(item) for item in question.standard_answer.split("|") if item.strip()]
    return answer in standards if standards else answer == standard
```

**文件 4：`frontend/public/stitch-pages/practice.html`**

确认并补齐展示：

1. `single_choice` / `multiple_choice`：选项按钮或 checkbox。
2. `judge`：正确/错误二选一。
3. `fill_blank`：单行输入框。
4. `short_answer`：多行文本框。
5. `coding`：多行代码文本框，第一版不做代码执行评测。

#### 验收 Gate

1. 后端测试：`QuizGenerateRequest(question_types=["judge","fill_blank","short_answer","coding"])` 能通过校验并生成 4 种题。
2. Mock Provider 测试：LLM 返回空或格式错误时，fallback 能分别生成判断、填空、简答、编程题，而不是全部退化为单选或简答。
3. 提交答案测试：判断题正确/错误能判分；填空题支持 `|` 同义答案；简答/编程题返回可解释反馈。
4. 前端测试：`/practice` 可以生成并提交至少判断、填空、简答三类题，页面无 JS error。

---

### T6: `generate_diagram` — 图解说明生成

**优先级**：P1（不依赖外部 API，Mermaid 实现）
**工时**：1-2 小时
**对应缺口**：赛题要求"图解说明"

#### 功能定义

```
工具名: generate_diagram
描述: 围绕知识概念生成流程图、架构图或示意图的 Mermaid 代码。
输入:
  - concept (string, required): 需要图解的概念
  - diagram_type (string, optional): 图表类型 "flowchart" / "sequence" / "class" / "er"，默认 "flowchart"
风险等级: low
writes_db: true
```

#### 实现方案

复用 `MindmapService` 的架构，但独立为 `DiagramService`，避免一个 service 同时承担 mindmap 和流程图逻辑。第一版仍保存到 `GeneratedResource.content`，`resource_type="diagram"`，不新增 `format/metadata` 字段。

需同步修改：

- `backend/app/schemas/resource.py`：`VALID_RESOURCE_TYPES` 增加 `diagram`，别名增加“图解/流程图/架构图/示意图”。
- `backend/app/services/resource_service.py`：`_default_title()` 增加 `diagram`。
- `backend/app/services/diagram_service.py`：新增服务。
- `backend/app/agent_runtime/service_tools.py`：注册 `generate_diagram`。
- `backend/app/agent_runtime/supervisor.py`：增加关键词触发和默认参数。

```python
DIAGRAM_PROMPTS = {
    "flowchart": "生成一个 Mermaid flowchart TD 流程图，展示 {concept} 的执行流程或逻辑关系。",
    "sequence": "生成一个 Mermaid sequenceDiagram 时序图，展示 {concept} 中各组件的交互过程。",
    "class": "生成一个 Mermaid classDiagram 类图，展示 {concept} 的结构和关系。",
    "er": "生成一个 Mermaid erDiagram 实体关系图，展示 {concept} 的数据模型。",
}
```

handler 示例：

```python
async def generate_diagram_handler(context: ToolContext, arguments: dict[str, Any]) -> ToolExecutionResult:
    from app.services.diagram_service import DiagramService

    result = await DiagramService(db).generate(
        current_user=current_user,
        course_id=context.course_id,
        concept=str(arguments.get("concept") or context.course_id),
        diagram_type=str(arguments.get("diagram_type") or "flowchart"),
    )
    return ToolExecutionResult(
        output=result,
        evidence=result.get("citations") or [],
        citations=result.get("citations") or [],
        artifact_refs=[
            {
                "type": "resource",
                "subtype": "diagram",
                "id": result["resource_id"],
                "title": result["title"],
            }
        ],
    )
```

Supervisor 默认参数：

```python
"generate_diagram": {"concept": goal, "diagram_type": "flowchart"},
```

#### 验收 Gate

1. 能生成 `flowchart TD`、`sequenceDiagram` 至少两类 Mermaid 图。
2. `generated_resources` 中 `resource_type="diagram"`，`content` 为 Mermaid 代码，`citations` 非空。
3. `/assistant` 能通过自然语言“画一个递归调用栈流程图”触发工具并显示 artifact。
4. 前端 Mermaid 渲染失败时显示代码文本兜底。

---

## 三、非工具类差距弥补

### S1: 防幻觉 + 内容安全过滤

**优先级**：P0（非功能性需求硬性要求）
**工时**：2-3 小时

#### 当前状态

- `ReviewAgent` 已能输出 `pass / issues / risk_level / revision_suggestions`，但事实校验主要依赖 LLM 审查，缺少规则层证据检查。
- `ResourceService`、`TutorService` 内已有“引用为空则中风险”的局部检查，但尚未抽成统一服务。
- 不建议维护大而空泛的“敏感词库”作为比赛核心卖点；第一版应做课程学习场景可解释安全规则：来源缺失、无依据学术断言、危险/违法/隐私请求、AI 推断未标注。

#### 实现方案

**新建文件**：`backend/app/services/content_safety_service.py`

```python
"""内容安全过滤服务 — 防幻觉 + 敏感词拦截。"""

class ContentSafetyService:
    """统一内容安全检查，所有 AI 生成内容可复用。"""

    BLOCKED_INTENT_PATTERNS = [
        "绕过考试监控",
        "代考",
        "窃取账号",
        "泄露隐私",
        "破解密码",
    ]

    UNSOURCED_CLAIM_MARKERS = [
        "据研究表明",
        "根据统计",
        "专家指出",
        "权威数据显示",
        "大量实验表明",
    ]

    async def check(
        self,
        content: str,
        *,
        citations: list[dict] | None = None,
        source_chunks: list[dict] | None = None,
        require_citation: bool = False,
    ) -> dict:
        """
        综合安全检查。
        返回: { safe: bool, risk_level: str, issues: list, suggestions: list }
        """
        issues = []
        suggestions = []
        citations = citations or []

        for pattern in self.BLOCKED_INTENT_PATTERNS:
            if pattern in content:
                issues.append(f"检测到不适合学习场景的请求或内容: {pattern}")
                suggestions.append("请拒绝该部分内容，并改为提供合规学习建议。")

        for marker in self.UNSOURCED_CLAIM_MARKERS:
            if marker in content:
                issues.append(f"疑似无来源学术声称: {marker}")
                suggestions.append("请补充具体课程资料引用，或标注“AI 推断内容，建议核对资料”。")

        if require_citation and not citations:
            issues.append("生成内容缺少引用来源")
            suggestions.append("请基于 RAG/Wiki 重新生成，或明确标注无可靠来源。")

        if source_chunks is not None and not source_chunks:
            if any(kw in content for kw in ["根据课程", "资料指出", "课本"]):
                issues.append("声称引用课程资料但未提供来源引用")
                suggestions.append("请添加具体 chunk 引用或标注“AI 推断内容，建议核对资料”。")

        risk_level = "high" if any("不适合学习场景" in item for item in issues) else "medium" if issues else "low"
        return {
            "safe": len(issues) == 0,
            "risk_level": risk_level,
            "issues": issues,
            "suggestions": suggestions,
        }
```

**集成到 `ReviewAgent`**：在 `review_agent.py` 的 `run()` 方法中，LLM 审查后增加安全检查：

```python
# 在 _parse_review 之后
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

safety = await ContentSafetyService().check(
    content,
    citations=context.params.get("citations") or [],
    source_chunks=context.params.get("source_chunks"),
    require_citation=bool(context.params.get("require_citation")),
)
if not safety["safe"]:
    current_risk = review.get("risk_level", "medium")
    safety_risk = safety["risk_level"]
    review["risk_level"] = current_risk if RISK_ORDER[current_risk] >= RISK_ORDER[safety_risk] else safety_risk
    review["issues"] = review.get("issues", []) + safety["issues"]
    review["revision_suggestions"] = review.get("revision_suggestions", []) + safety["suggestions"]
```

**集成到 `service_tools.py` 的 `review_artifacts`**：工具执行前自动过安全检查。

#### 验收 Gate

1. 单元测试：无引用但声明“根据课程资料”的内容被标记 medium。
2. 单元测试：包含“代考/破解密码/泄露隐私”等学习场景不合规意图时标记 high。
3. ReviewAgent 测试：LLM 审查低风险但规则审查中风险时，最终风险提升到 medium。
4. Tutor/Resource 生成结果如果 `citations=[]`，前端显示“AI 推断内容，建议核对资料”或 Review 风险提示。

---

### S2: 资源主动推送机制

**优先级**：P1（核心功能第③条）
**工时**：2-3 小时

#### 当前状态

- `refresh_recommendations` 是被动调用
- 无基于画像变化自动触发推送
- `RecommendationService.refresh_recommendations()` 当前需要 `current_user: User` 和 `course_id`，不能在 `ProfileService` 中用 `current_user=...` 占位硬调。

#### 实现方案

采用“轻量事件 + 后台/后续工具刷新”的方式，不把 `ProfileService` 和 `RecommendationService` 强耦合。

**第一步：画像/诊断变化写学习事件**

在 `profile_service.py` 的 `ingest_dialogue_profile()` 提交成功后写入 `learning_records`：

```python
from app.services.learning_record_service import LearningRecordService

if course_id is not None:
    await LearningRecordService(self.db).record_event(
        user_id=user_id,
        course_id=course_id,
        event_type="profile_updated",
        event_source="profile_service",
        event_payload={
            "source": "dialogue_ingest",
            "changed_fields": list(signals.keys()),
            "source_message_id": source_message_id,
        },
        commit=False,
    )
```

在 `diagnosis_service.py` 的 `analyze()` 报告保存后写入事件：

```python
await LearningRecordService(self.db).record_event(
    user_id=current_user.id,
    course_id=course_id,
    event_type="diagnosis_generated",
    event_source="diagnosis_service",
    event_payload={
        "report_id": str(report.id),
        "weak_points_count": len(weak_points),
        "recommended_actions_count": len(recommended_actions),
    },
    commit=False,
)
```

注意：如果事件写入和业务对象在同一事务中，应统一 `commit=False`，最后由原 service 的 commit 收口，避免半成功。

**第二步：新增推荐刷新调度工具**

优先复用已有 `refresh_recommendations` Agent 工具，不新建表。增强工具描述，让 Supervisor 在“画像更新后推荐 / 根据诊断推送资源”等目标中主动调用它。

在 `supervisor.py` 的 `_required_tools()` 中增加关键词：

```python
("refresh_recommendations", ("根据画像推送", "主动推荐", "刷新推荐", "诊断后推荐", "推荐资源")),
```

**第三步：前端呈现“主动推送”**

在 `/dashboard` 和 `/path-profile` 中读取 `GET /api/v1/recommendations`，当有 pending 推荐时显示：

```text
基于你的最新画像/诊断，系统已刷新 3 条推荐
```

不需要 Web Push，也不需要浏览器通知权限；比赛演示中的“主动推送”以“画像/诊断完成后自动刷新推荐卡片”作为第一版定义。

#### 后续增强（可选）

如果要做到真正后台自动刷新，可在 arq Worker 中增加 `recommendation_refresh` 任务：

1. 画像/诊断 service 只 enqueue `user_id/course_id/reason`；
2. Worker 从数据库加载 `User`；
3. 调用 `RecommendationService.refresh_recommendations(current_user=user, course_id=course_id)`；
4. 写入 `agent_task_events` 或 `learning_records` 作为推送证据。

#### 验收 Gate

1. 对话式画像更新后写入 `learning_records.event_type="profile_updated"`。
2. 诊断生成后写入 `learning_records.event_type="diagnosis_generated"`。
3. 用户说“根据我的最新画像主动推荐下一步资源”，Supervisor 能调用 `refresh_recommendations`。
4. `/dashboard` 或 `/path-profile` 能展示 pending 推荐及推荐理由。

---

### S3: 学习行为实时追踪

**优先级**：P1（加分项第⑤条）
**工时**：3-4 小时

#### 当前状态

- `learning_records` 只有手动记录 API
- 无前端埋点
- 当前前端业务请求集中在 `frontend/public/stitch-pages/zhixue-static-api.js`，不应优先新建只服务 React 页面的 `frontend/lib/analytics.ts`。

#### 实现方案

**后端：新增 API 端点**

`backend/app/api/v1/learning_records.py` 中已有 `list_records`，需要新增批量记录端点。

新建 `backend/app/schemas/learning_record.py`：

```python
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


ALLOWED_LEARNING_EVENT_TYPES = {
    "page_view",
    "resource_read",
    "quiz_start",
    "quiz_complete",
    "wiki_read",
    "tutor_ask",
    "practice_mistake",
    "profile_updated",
    "diagnosis_generated",
    "recommendation_view",
    "recommendation_click",
}


class LearningEventCreate(BaseModel):
    course_id: UUID | None = None
    knowledge_id: UUID | None = None
    event_type: str = Field(min_length=1, max_length=64)
    event_source: str | None = Field(default="frontend", max_length=64)
    event_payload: dict[str, Any] = Field(default_factory=dict)


class LearningEventBatchRequest(BaseModel):
    events: list[LearningEventCreate] = Field(min_length=1, max_length=50)
```

API 端点：

```python
@router.post("/events/batch")
async def record_learning_events(
    request: Request,
    payload: LearningEventBatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量记录学习行为事件。"""
    service = LearningRecordService(db)
    for event in payload.events:
        if event.event_type not in ALLOWED_LEARNING_EVENT_TYPES:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail=f"不支持的学习行为类型: {event.event_type}",
                status_code=400,
            )
        await service.record_event(
            user_id=current_user.id,
            course_id=event.course_id,
            knowledge_id=event.knowledge_id,
            event_type=event.event_type,
            event_source=event.event_source,
            event_payload=event.event_payload,
            commit=False,
        )
    await db.commit()
    return success_response({"recorded": len(payload.events)}, request=request)
```

**前端：Stitch 行为埋点工具**

修改 `frontend/public/stitch-pages/zhixue-static-api.js`，暴露 `trackLearningEvent()` 和 `trackLearningEvents()`：

```javascript
async function trackLearningEvents(events) {
  try {
    if (!Array.isArray(events) || !events.length) return { recorded: 0 };
    return await request("/learning-records/events/batch", {
      method: "POST",
      body: {
        events: events.map((event) => ({
          ...event,
          event_source: event.event_source || "stitch_frontend",
          event_payload: event.event_payload || {},
        })),
      },
    });
  } catch {
    return { recorded: 0, ignored: true };
  }
}

async function trackLearningEvent(event) {
  return trackLearningEvents([event]);
}
```

在导出的 `window.zhixue` 对象中增加：

```javascript
trackLearningEvent,
trackLearningEvents,
```

**埋点位置（第一版只做关键行为，不铺满页面）**

| 页面 | 事件 | 触发点 |
|---|---|---|
| `/knowledge` | `wiki_read` | 打开 Wiki 详情 |
| `/assistant` | `tutor_ask` | 发送 Agent/Tutor 问题 |
| `/practice` | `quiz_start` | 生成或开始答题 |
| `/practice` | `quiz_complete` | 提交答案后 |
| `/dashboard` | `recommendation_view` | 推荐卡加载 |
| `/dashboard` | `recommendation_click` | 点击推荐 |

#### 验收 Gate

1. `POST /api/v1/learning-records/events/batch` 出现在 OpenAPI 和 `16_当前实现API清单.md` 中，因此本任务完成后必须执行 `python scripts/export_implementation_docs.py`。
2. API 测试：批量提交 2 条事件，返回 `recorded=2`，数据库 `learning_records` 新增 2 条当前用户记录。
3. API 测试：提交不支持的 `event_type` 返回参数错误。
4. 前端手动验收：打开 Wiki、提问、提交练习后，`GET /api/v1/learning-records` 能看到对应事件。

---

### S4: 策略动态调整闭环

**优先级**：P1（加分项第⑤条）
**工时**：2 小时

#### 实现方案

自进化边界要求“可解释、可记录、可版本化、可回滚、有证据、有风险等级”。因此第一版不做静默自动应用，改为：

```text
诊断/行为事件显示学习效果下降
  → 自动生成 draft 自进化策略
  → low 风险策略可在前端给出“建议应用”按钮
  → medium/high 仍需要用户或管理员确认
```

在 `evolution_service.py` 中增加受控分析入口：

```python
async def auto_evolve_if_needed(self, user_id: UUID, course_id: UUID):
    """诊断后自动判断是否需要生成自进化策略草稿。"""
    diagnosis = await self._get_latest_diagnosis(user_id, course_id)
    if not diagnosis:
        return None

    accuracy_rate = diagnosis.get("accuracy_rate", 1.0)
    weak_points = diagnosis.get("weak_points") or []
    if accuracy_rate >= 0.6 and len(weak_points) < 2:
        return None

    result = await self.analyze(
        current_user=await self._get_user(user_id),
        payload=AnalyzeRequest(
            course_id=course_id,
            trigger_type="auto_diagnosis",
            focus="根据最近诊断自动生成学习策略草稿，不自动应用。",
            evidence={
                "diagnosis_id": str(diagnosis["id"]),
                "accuracy_rate": accuracy_rate,
                "weak_points": weak_points[:5],
            },
        )
    )
    return result
```

触发位置：

1. `DiagnosisService.analyze(..., trigger_evolution=True)` 时调用；
2. 或由 Agent 工具 `analyze_learning_diagnosis` 在诊断完成后调用 `evolution/analyze`；
3. 前端 `/path-profile` 展示新增 draft 策略，用户点击后仍走现有 `apply_evolution_strategy` 高风险确认链路。

#### 验收 Gate

1. 诊断正确率低或薄弱点多时生成 `evolution_strategies.status="draft"`。
2. 不出现静默应用策略；`active` 状态只由用户确认后的 apply 操作产生。
3. 策略 evidence 包含诊断报告 ID、薄弱点、触发原因。
4. `/path-profile` 能展示草稿策略、风险等级、应用/回滚入口。

---

## 四、完整文件改动清单

| 文件 | 改动类型 | 涉及工具 |
|------|---------|---------|
| `backend/app/agent_runtime/service_tools.py` | 新增 5 个工具注册 + 1 个扩展 | T1-T6 |
| `backend/app/agent_runtime/supervisor.py` | 新增关键词触发规则 | T1-T6 |
| `backend/app/llm/audio_provider.py` | **新建**：Audio Provider 抽象、Mock、真实 Provider | T3, T4 |
| `backend/app/schemas/resource.py` | 扩展 `VALID_RESOURCE_TYPES` / aliases | T2, T6 |
| `backend/app/services/mindmap_service.py` | **新建** | T2 |
| `backend/app/services/diagram_service.py` | **新建** | T6 |
| `backend/app/services/content_safety_service.py` | **新建** | S1 |
| `backend/app/services/resource_service.py` | 扩展资源类型校验和标题映射 | T2, T6 |
| `backend/app/services/prompt_service.py` | 扩展 quiz.generate Prompt 多题型契约 | T5 |
| `backend/app/services/quiz_service.py` | 扩展题型处理 | T5 |
| `backend/app/agents/quiz_agent.py` | 扩展 prompt 支持多题型 | T5 |
| `backend/app/services/profile_service.py` | 画像变化写 learning_records 事件 | S2 |
| `backend/app/services/diagnosis_service.py` | 诊断后写事件，可触发策略草稿 | S2, S4 |
| `backend/app/services/evolution_service.py` | 增加受控策略草稿生成 | S4 |
| `backend/app/api/v1/learning_records.py` | 新增批量事件记录端点 | S3 |
| `backend/app/schemas/learning_record.py` | 新增批量请求 schema | S3 |
| `frontend/public/stitch-pages/zhixue-static-api.js` | 暴露 `trackLearningEvent(s)` | S3 |
| `frontend/public/stitch-pages/assistant.html` | 语音入口、朗读按钮、artifact 展示增强 | T2-T4, T6 |
| `frontend/public/stitch-pages/knowledge.html` | Mermaid 资源展示入口（可选，第一版可先在 assistant 展示） | T2, T6 |
| `frontend/public/stitch-pages/practice.html` | 多题型展示和提交 | T5 |
| `frontend/public/stitch-pages/dashboard.html` | 推荐主动推送展示 | S2, S3 |
| `frontend/public/stitch-pages/path-profile.html` | 策略草稿和风险展示 | S4 |
| `docs/change_2-工具拓展与差距弥补推进方案.md` | **本文件** | 全部 |

---

## 五、实施顺序与时间估算

### 第一批（立即，1-2 天）

| 序号 | 任务 | 工时 | 依赖 |
|------|------|------|------|
| 1 | T1: `parse_uploaded_document` 工具 | 1-1.5h | 无 |
| 2 | T2: `generate_mindmap` + 资源类型扩展 | 2-3h | 资源类型常量 |
| 3 | T6: `generate_diagram` + Mermaid artifact | 2-3h | 复用 T2 资源模式 |
| 4 | T5: 扩展 quiz 多题型 Prompt / fallback / 前端 | 2-4h | 无 |
| 5 | S1: 防幻觉 + 内容安全服务 | 2-3h | ReviewAgent |

### 第二批（3-5 天）

| 序号 | 任务 | 工时 | 依赖 |
|------|------|------|------|
| 6 | S3: 学习行为追踪 API + Stitch 埋点 | 4-6h | 需更新 OpenAPI 文档 |
| 7 | S2: 资源主动推送展示 | 2-3h | S3 事件更完整 |
| 8 | T3: `transcribe_audio` + MiMo Token Plan Audio Provider | 2-3h | 真实 MiMo 优先，Mock 兜底 |
| 9 | T4: `synthesize_speech` | 1-2h | 依赖 T3 Provider，覆盖三种 MiMo TTS 模型 |

### 第三批（比赛前）

| 序号 | 任务 | 工时 | 依赖 |
|------|------|------|------|
| 10 | S4: 策略动态调整草稿闭环 | 2-3h | S2/S3/S1 |
| 11 | 演示数据一键初始化 | 3-5h | 核心工具就绪 |
| 12 | 浏览器 E2E 演示链路 | 3-5h | 前端接入完成 |
| 13 | Docker Compose 全栈验证 | 2-4h | 非日常开发阻塞项，部署专项执行 |

---

## 六、扩展后的完整工具清单（17 个）

| # | 工具名 | 功能 | risk | 新增 |
|---|--------|------|------|------|
| 1 | `search_course_knowledge` | RAG 检索 | low | |
| 2 | `answer_course_question` | AI 答疑 | low | |
| 3 | `generate_learning_path` | 学习路径 | low | |
| 4 | `generate_explanation` | 讲解文档/总结/案例 | low | |
| 5 | `generate_quiz` | 练习题（6 种题型） | low | **扩展** |
| 6 | `analyze_learning_diagnosis` | 学习诊断 | low | |
| 7 | `refresh_recommendations` | 资源推荐 | low | |
| 8 | `update_profile_from_dialogue` | 对话式画像 | low | |
| 9 | `rebuild_profile` | 画像重建 | low | |
| 10 | `reflect_learning_memory` | 长期记忆 | low | |
| 11 | `review_artifacts` | 内容审查（+安全过滤） | low | **增强** |
| 12 | `apply_evolution_strategy` | 自进化策略 | high | |
| 13 | `parse_uploaded_document` | 文档解析 | low | 🆕 |
| 14 | `transcribe_audio` | 语音转文字 | low | 🆕 |
| 15 | `synthesize_speech` | 文字转语音 | low | 🆕 |
| 16 | `generate_mindmap` | 思维导图 | low | 🆕 |
| 17 | `generate_diagram` | 图解说明 | low | 🆕 |

---

## 七、赛题功能覆盖度对照

| 赛题要求 | 覆盖工具 | 状态 |
|---------|---------|------|
| ① 对话式画像 ≥6 维度 | `update_profile_from_dialogue` | ✅ 已有 |
| ② 多智能体协同 ≥5 类资源 | `generate_explanation` + `generate_quiz`(6型) + `generate_mindmap` + `generate_diagram` + `generate_learning_path` | ✅ 5+ 类 |
| ③ 个性化学习路径 + 推荐 | `generate_learning_path` + `refresh_recommendations` + 主动推送 | ✅ 增强 |
| ④ 智能辅导（多模态） | `answer_course_question` + `transcribe_audio` + `synthesize_speech` | ✅ 增强 |
| ⑤ 学习效果评估 | `analyze_learning_diagnosis` + 行为追踪 + 策略自动调整 | ✅ 增强 |
| 防幻觉 + 安全 | `review_artifacts` + `ContentSafetyService` | ✅ 新增 |
| 流式输出 | 现有 Agent SSE + 新工具 artifact/progress | ✅ 增强 |
| 外部 AI 工具说明 | MiMo/其他外部 Provider + Mock 兜底 | ✅ 增强 |
