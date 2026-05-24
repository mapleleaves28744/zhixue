# 多智能体基础框架设计

## Context

智学工坊项目需要多智能体协作能力来支撑核心学习链路（文档解析 → Wiki 生成 → AI 答疑 → 练习诊断 → 自进化策略）。当前后端已有完整的 LLM 基础设施（Provider、适配器、调用日志），但缺少 Agent 抽象层。本设计为第 9 阶段（T09-01 ~ T09-04）建立多智能体框架。

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Agent-Service 交互 | 构造器注入 `AsyncSession` | 与现有 tutor.py 模式一致，无需引入 DI 框架 |
| 任务执行模式 | Agent 链式执行 | 支持未来多 Agent 协作（如 WikiAgent → ReviewAgent），MVP 实际为单 Agent |
| 路由方式 | 硬编码 `TASK_AGENT_PLAN` 映射表 | MVP 够用，无需动态配置 |
| Agent 注册 | 装饰器 `@AgentRegistry.register` | 自动注册，无需手动维护列表 |

## 文件清单

### 新增文件
| 文件 | 用途 |
|------|------|
| `backend/app/agents/context.py` | AgentContext、AgentResult 数据类 |
| `backend/app/agents/base_agent.py` | BaseAgent 抽象基类 |
| `backend/app/agents/registry.py` | AgentRegistry 注册表 |
| `backend/app/agents/orchestrator.py` | OrchestratorAgent 编排器 |
| `backend/app/models/agent.py` | AgentRun ORM 模型 |
| `backend/app/services/agent_log_service.py` | Agent 运行日志服务 |
| `backend/app/services/agent_service.py` | Agent 任务执行入口 |
| `backend/app/agents/wiki_agent.py` | WikiAgent |
| `backend/app/agents/tutor_agent.py` | TutorAgent |
| `backend/app/agents/knowledge_agent.py` | KnowledgeAgent |
| `backend/app/agents/quiz_agent.py` | QuizAgent |
| `backend/app/agents/resource_agent.py` | ResourceAgent |
| `backend/app/agents/diagnosis_agent.py` | DiagnosisAgent |
| `backend/app/agents/recommend_agent.py` | RecommendAgent |
| `backend/app/agents/evolution_agent.py` | EvolutionAgent |
| `backend/app/agents/review_agent.py` | ReviewAgent |
| `backend/app/agents/planner_agent.py` | PlannerAgent |
| `backend/app/agents/profile_agent.py` | ProfileAgent |
| `backend/app/agents/memory_agent.py` | MemoryAgent（MVP 占位） |
| `backend/alembic/versions/20260523_2200_xxx_create_agent_runs.py` | agent_runs 迁移 |

### 修改文件
| 文件 | 变更 |
|------|------|
| `backend/app/agents/__init__.py` | 导入所有 Agent 触发注册 |
| `backend/app/models/__init__.py` | 添加 AgentRun 导出 |
| `backend/app/api/v1/agents.py` | 扩展为完整 CRUD 端点 |
| `backend/app/api/v1/router.py` | 已包含 agents 路由（无需改动） |

## 详细设计

### 1. 核心类型（T09-01）

**`backend/app/agents/context.py`**

```python
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class AgentContext:
    """Agent 输入上下文"""
    user_id: UUID
    course_id: UUID
    task_type: str                          # e.g. "document_to_wiki", "course_qa"
    params: dict[str, Any] = field(default_factory=dict)   # 任务特定参数
    metadata: dict[str, Any] = field(default_factory=dict) # 链式传递的中间数据
    run_id: UUID | None = None              # 当前 agent_runs 记录 ID，由 Orchestrator 设置


@dataclass
class AgentResult:
    """Agent 统一返回"""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    evidence: list[str] = field(default_factory=list)      # 决策依据
    next_actions: list[str] = field(default_factory=list)  # 建议后续动作
```

**`backend/app/agents/base_agent.py`**

```python
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import AgentContext, AgentResult


class BaseAgent(ABC):
    """Agent 抽象基类"""
    name: str
    description: str

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult: ...

    def success_result(
        self,
        data: dict[str, Any] | None = None,
        message: str = "",
        evidence: list[str] | None = None,
        next_actions: list[str] | None = None,
    ) -> AgentResult:
        return AgentResult(
            success=True,
            data=data or {},
            message=message,
            evidence=evidence or [],
            next_actions=next_actions or [],
        )

    def error_result(self, message: str = "", **kwargs: Any) -> AgentResult:
        return AgentResult(success=False, message=message, **kwargs)
```

### 2. Registry 与 Orchestrator（T09-02）

**`backend/app/agents/registry.py`**

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.agents.base_agent import BaseAgent


class AgentRegistry:
    """Agent 注册表，通过装饰器自动注册"""
    _registry: dict[str, type[BaseAgent]] = {}

    @classmethod
    def register(cls, agent_class: type[BaseAgent]) -> type[BaseAgent]:
        cls._registry[agent_class.name] = agent_class
        return agent_class

    @classmethod
    def get(cls, name: str) -> type[BaseAgent] | None:
        return cls._registry.get(name)

    @classmethod
    def all(cls) -> dict[str, type[BaseAgent]]:
        return dict(cls._registry)
```

**`backend/app/agents/orchestrator.py`**

```python
from time import perf_counter
from app.agents.base_agent import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.registry import AgentRegistry
from app.services.agent_log_service import AgentLogService

# 硬编码任务计划：task_type → Agent 名称列表
TASK_AGENT_PLAN: dict[str, list[str]] = {
    "document_to_wiki": ["WikiAgent"],
    "course_qa": ["TutorAgent"],
    "extract_knowledge": ["KnowledgeAgent"],
    "generate_quiz": ["QuizAgent"],
    "generate_resource": ["ResourceAgent"],
    "diagnose_student": ["DiagnosisAgent"],
    "recommend_resources": ["RecommendAgent"],
    "evolve_strategy": ["EvolutionAgent"],
    "review_content": ["ReviewAgent"],
    "plan_learning": ["PlannerAgent"],
    "update_profile": ["ProfileAgent"],
}


class OrchestratorAgent(BaseAgent):
    """任务编排器，按计划链式调用 Agent"""
    name = "OrchestratorAgent"
    description = "根据 task_type 路由到对应 Agent 链执行"

    async def run(self, context: AgentContext) -> AgentResult:
        plan = TASK_AGENT_PLAN.get(context.task_type)
        if not plan:
            return self.error_result(message=f"未知任务类型: {context.task_type}")

        log_service = AgentLogService(self.db)
        result: AgentResult | None = None
        for agent_name in plan:
            agent_cls = AgentRegistry.get(agent_name)
            if agent_cls is None:
                return self.error_result(message=f"Agent 未注册: {agent_name}")

            # 记录日志：开始
            run_log = await log_service.start_run(
                task_type=context.task_type,
                agent_name=agent_name,
                input_payload={"params": context.params, "metadata": context.metadata},
            )
            started = perf_counter()

            try:
                agent = agent_cls(db=self.db)
                result = await agent.run(context)
            except Exception as exc:
                # 记录日志：异常
                await log_service.finish_run(
                    run_id=run_log.id,
                    output_payload={},
                    status="failed",
                    duration_ms=int((perf_counter() - started) * 1000),
                    error_message=str(exc),
                )
                return self.error_result(message=f"Agent {agent_name} 执行异常: {exc}")

            # 记录日志：完成
            await log_service.finish_run(
                run_id=run_log.id,
                output_payload=result.data,
                status="success" if result.success else "failed",
                duration_ms=int((perf_counter() - started) * 1000),
                error_message=result.message if not result.success else None,
            )

            if not result.success:
                return result  # fail-fast
            context.metadata.update(result.data)

        return result  # type: ignore[return-value]
```

**`backend/app/services/agent_service.py`**

```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import AgentContext
from app.agents.orchestrator import OrchestratorAgent
from app.agents.context import AgentResult


class AgentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_task(
        self,
        task_type: str,
        user_id: UUID,
        course_id: UUID,
        params: dict | None = None,
    ) -> AgentResult:
        context = AgentContext(
            user_id=user_id,
            course_id=course_id,
            task_type=task_type,
            params=params or {},
        )
        orchestrator = OrchestratorAgent(db=self.db)
        return await orchestrator.run(context)
```

### 3. Agent 运行日志（T09-03）

**`backend/app/models/agent.py`**

```python
class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("idx_agent_runs_user_course", "user_id", "course_id"),
        Index("idx_agent_runs_task_type", "task_type"),
        Index("idx_agent_runs_status", "status"),
    )

    id: UUID                    # PK, gen_random_uuid()
    user_id: UUID | None        # FK → users.id, SET NULL
    course_id: UUID | None      # FK → courses.id, SET NULL
    task_type: str(64)
    agent_name: str(128)
    input_payload: JSONB        # server_default '{}'
    output_payload: JSONB       # server_default '{}'
    status: str(32)             # "running" | "success" | "failed"
    duration_ms: int | None
    error_message: Text | None
    created_at: DateTime        # server_default now()
```

**日志集成**：OrchestratorAgent.run() 在每个 Agent 执行前后自动写入 agent_runs 记录。执行前 status="running"，成功后更新为 "success"，异常更新为 "failed"。

**LLM 调用关联**：Agent 内部调用 LLM 时，需将 `agent_run_id` 传入 `get_llm_provider()`，使 `llm_call_logs.agent_run_id` 字段与 `agent_runs.id` 关联。这通过在 `AgentContext` 中新增 `run_id: UUID | None` 字段实现——Orchestrator 在调用 Agent.run() 前设置该字段，Agent 内部读取并传给 LLM Provider。`context.py` 中的 `AgentContext` 需增加此字段。

**`backend/app/services/agent_log_service.py`**

```python
class AgentLogService:
    def __init__(self, db: AsyncSession) -> None: ...

    async def start_run(self, task_type, agent_name, input_payload) -> AgentRun: ...
    async def finish_run(self, run_id, output_payload, status, duration_ms, error_message=None) -> AgentRun: ...
    async def list_runs(self, user_id, course_id=None, task_type=None, status=None, page=1, page_size=20) -> tuple[list[AgentRun], int]: ...
    async def get_run(self, run_id) -> AgentRun | None: ...
```

**API 端点** `backend/app/api/v1/agents.py`：

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/agents/run` | 执行 Agent 任务 |
| GET | `/agents/runs` | 查询运行列表（分页） |
| GET | `/agents/runs/{run_id}` | 查询运行详情 |

### 4. MVP Agent 类（T09-04）

所有 Agent 使用 `@AgentRegistry.register` 装饰器自动注册。每个 Agent 的 `run()` 方法编排已有 Service：

**示例 — WikiAgent**：
```python
@AgentRegistry.register
class WikiAgent(BaseAgent):
    name = "WikiAgent"
    description = "将课程资料转换为 Wiki 页面"

    async def run(self, context: AgentContext) -> AgentResult:
        # 1. 读取 material
        material_service = MaterialService(self.db)
        material = await material_service.get_material(context.params["material_id"])

        # 2. RAG 检索相关片段
        retriever = VectorRetriever(self.db)
        chunks = await retriever.search(course_id=context.course_id, query=material.title)

        # 3. 调用 LLM 生成 Wiki
        prompts = PromptService(self.db)
        rendered = await prompts.render_prompt(
            agent_name="WikiAgent", scene="wiki.generate",
            params={"title": material.title, "content": material.content[:3000], "context": ...}
        )
        llm = get_llm_provider(db=self.db, user_id=context.user_id, course_id=context.course_id)
        response = await llm.chat([ChatMessage(role="user", content=rendered.content)])

        return self.success_result(
            data={"wiki_content": response.content, "material_id": str(material.id)},
            message="Wiki 生成成功",
            evidence=[f"基于 {len(chunks)} 个文档片段检索"],
        )
```

**示例 — TutorAgent**（复用 tutor.py 逻辑）：
```python
@AgentRegistry.register
class TutorAgent(BaseAgent):
    name = "TutorAgent"
    description = "基于 RAG 的课程问答"

    async def run(self, context: AgentContext) -> AgentResult:
        question = context.params.get("question", "")
        retriever = VectorRetriever(self.db)
        results = await retriever.search(course_id=context.course_id, query=question)
        # ... 复用 tutor.py 的 PromptService + LLM 调用逻辑
```

**MemoryAgent**（MVP 占位）：
```python
@AgentRegistry.register
class MemoryAgent(BaseAgent):
    name = "MemoryAgent"
    description = "管理 Agent 记忆和上下文"

    async def run(self, context: AgentContext) -> AgentResult:
        return self.success_result(data={"placeholder": True}, message="MemoryAgent MVP 占位")
```

### 5. 导入注册（`agents/__init__.py`）

```python
# 导入所有 Agent 触发 @AgentRegistry.register 装饰器
from app.agents.wiki_agent import WikiAgent
from app.agents.tutor_agent import TutorAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.resource_agent import ResourceAgent
from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.recommend_agent import RecommendAgent
from app.agents.evolution_agent import EvolutionAgent
from app.agents.review_agent import ReviewAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.profile_agent import ProfileAgent
from app.agents.memory_agent import MemoryAgent

__all__ = [
    "WikiAgent", "TutorAgent", "KnowledgeAgent", "QuizAgent",
    "ResourceAgent", "DiagnosisAgent", "RecommendAgent", "EvolutionAgent",
    "ReviewAgent", "PlannerAgent", "ProfileAgent", "MemoryAgent",
]
```

## 验证方案

1. **类型检查**：`cd backend && python -c "from app.agents import *; print('OK')"`
2. **注册验证**：`python -c "from app.agents.registry import AgentRegistry; from app.agents import *; print(len(AgentRegistry.all()))"` 应输出 12
3. **API 测试**：
   - `POST /api/v1/agents/run` body: `{"task_type": "course_qa", "course_id": "...", "params": {"question": "什么是机器学习"}}`
   - `GET /api/v1/agents/runs` 验证日志记录
4. **数据库迁移**：`cd backend && alembic upgrade head` 验证 agent_runs 表创建成功
5. **Orchestrator 错误处理**：传入未知 task_type 验证返回明确错误
