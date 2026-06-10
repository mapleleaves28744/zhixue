"""生成器插件注册表。

使用 @GeneratorRegistry.register 装饰器注册生成器，
通过 resource_type 字符串查找并调用对应生成器。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.generators.base import BaseGenerator

logger = logging.getLogger(__name__)


class GeneratorRegistry:
    """生成器注册表 — 装饰器注册 + 按类型查找。"""

    _registry: dict[str, type[Any]] = {}

    @classmethod
    def register(cls, generator_cls: type[Any]) -> type[Any]:
        """装饰器：注册一个生成器类。"""
        resource_type = getattr(generator_cls, "resource_type", "")
        if not resource_type:
            raise ValueError(f"{generator_cls.__name__} 必须定义 resource_type")
        cls._registry[resource_type] = generator_cls
        logger.debug("GeneratorRegistry: registered '%s' -> %s", resource_type, generator_cls.__name__)
        return generator_cls

    @classmethod
    def get(cls, resource_type: str) -> type[Any] | None:
        """按 resource_type 查找生成器类。"""
        return cls._registry.get(resource_type)

    @classmethod
    def list_types(cls) -> list[str]:
        """列出所有已注册的资源类型。"""
        return list(cls._registry.keys())

    @classmethod
    async def generate(
        cls,
        resource_type: str,
        *,
        knowledge_name: str,
        context: str,
        profile_text: str = "",
        requirement: str = "",
        llm_provider: Any = None,
        **kwargs: Any,
    ) -> Any:
        """查找并调用指定类型的生成器。

        如果未注册对应类型，返回失败结果。
        """
        from app.generators.base import GeneratorResult

        gen_cls = cls.get(resource_type)
        if gen_cls is None:
            return GeneratorResult(
                content="",
                success=False,
                error_message=f"未注册的资源类型: {resource_type}",
                resource_type=resource_type,
            )

        generator = gen_cls()
        try:
            return await generator.generate(
                knowledge_name=knowledge_name,
                context=context,
                profile_text=profile_text,
                requirement=requirement,
                llm_provider=llm_provider,
                **kwargs,
            )
        except Exception as exc:
            logger.exception("Generator '%s' failed", resource_type)
            return GeneratorResult(
                content="",
                success=False,
                error_message=f"生成器执行失败: {exc}",
                resource_type=resource_type,
            )

    @classmethod
    def reset(cls) -> None:
        """清空注册表（仅用于测试）。"""
        cls._registry.clear()
