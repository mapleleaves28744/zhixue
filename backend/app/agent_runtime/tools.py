from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal
from uuid import UUID

from jsonschema import Draft202012Validator, ValidationError as JsonSchemaValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolContext:
    task_id: UUID
    tool_call_id: str
    user_id: UUID
    course_id: UUID
    conversation_id: UUID | None = None
    idempotency_key_override: str | None = None

    @property
    def idempotency_key(self) -> str:
        return self.idempotency_key_override or f"{self.task_id}:{self.tool_call_id}"


@dataclass
class ToolExecutionResult:
    success: bool = True
    output: dict[str, Any] = field(default_factory=dict)
    evidence: list[Any] = field(default_factory=list)
    artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    citations: list[Any] = field(default_factory=list)
    error_message: str | None = None
    attempts: int = 1
    final_answer: str | None = None


ToolHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[ToolExecutionResult]]
ResultLoader = Callable[[str], Awaitable[ToolExecutionResult | None]]
ResultSaver = Callable[[str, ToolExecutionResult], Awaitable[None]]
HandlerErrorRecovery = Callable[[Exception], Awaitable[None]]


@dataclass
class AgentTool:
    name: str
    description: str
    agent_name: str
    input_schema: dict[str, Any]
    handler: ToolHandler
    risk_level: Literal["low", "medium", "high"] = "low"
    writes_db: bool = False
    requires_confirmation: bool = False
    timeout_seconds: int = 120
    max_retries: int = 2

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


class ToolRegistry:
    def __init__(
        self,
        *,
        result_loader: ResultLoader | None = None,
        result_saver: ResultSaver | None = None,
        on_handler_error: HandlerErrorRecovery | None = None,
    ) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._results: dict[str, ToolExecutionResult] = {}
        self._result_loader = result_loader
        self._result_saver = result_saver
        self._on_handler_error = on_handler_error

    def register(self, tool: AgentTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具已注册: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"未知工具: {name}")
        return tool

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [tool.as_openai_tool() for tool in self._tools.values()]

    def requires_confirmation(self, name: str) -> bool:
        return self.get(name).requires_confirmation

    def risk_level(self, name: str) -> str:
        return self.get(name).risk_level

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolExecutionResult:
        tool = self.get(name)
        cached = self._results.get(context.idempotency_key)
        if cached is not None:
            return cached
        if self._result_loader is not None:
            persisted = await self._result_loader(context.idempotency_key)
            if persisted is not None:
                self._results[context.idempotency_key] = persisted
                return persisted
        try:
            self._validate_arguments(tool, arguments)
        except ValueError as exc:
            result = ToolExecutionResult(
                success=False,
                error_message=str(exc)[:2000],
                attempts=1,
            )
            self._results[context.idempotency_key] = result
            await self._save_result_safely(context.idempotency_key, result)
            return result
        attempts = 0
        last_error: Exception | None = None
        while attempts <= tool.max_retries:
            attempts += 1
            try:
                result = await asyncio.wait_for(
                    tool.handler(context, arguments),
                    timeout=tool.timeout_seconds,
                )
            except Exception as exc:
                last_error = exc
                continue
            result.attempts = attempts
            self._results[context.idempotency_key] = result
            await self._save_result_safely(context.idempotency_key, result)
            return result
        result = ToolExecutionResult(
            success=False,
            error_message=str(last_error or "工具执行失败")[:2000],
            attempts=attempts,
        )
        if last_error is not None:
            await self._recover_from_handler_error(last_error)
        self._results[context.idempotency_key] = result
        await self._save_result_safely(context.idempotency_key, result)
        return result

    async def _save_result_safely(self, key: str, result: ToolExecutionResult) -> None:
        if self._result_saver is None:
            return
        try:
            await self._result_saver(key, result)
        except Exception:
            logger.exception("Agent tool result persistence failed for %s", key)

    async def _recover_from_handler_error(self, error: Exception) -> None:
        if self._on_handler_error is None:
            return
        try:
            await self._on_handler_error(error)
        except Exception:
            logger.exception("Agent tool handler recovery failed")

    def _validate_arguments(self, tool: AgentTool, arguments: dict[str, Any]) -> None:
        schema = tool.input_schema or {"type": "object"}
        try:
            Draft202012Validator(schema).validate(arguments)
        except JsonSchemaValidationError as exc:
            path = ".".join(str(p) for p in exc.path)
            location = f" 参数 {path}" if path else ""
            raise ValueError(f"工具 {tool.name}{location} 校验失败: {exc.message}") from exc
