from __future__ import annotations

import string
from typing import Any

from app.core.error_codes import ErrorCode
from app.core.exceptions import BusinessException


class PromptRenderer:
    def render(self, template: str, params: dict[str, Any]) -> str:
        missing = self._missing_variables(template, params)
        if missing:
            raise BusinessException(
                code=ErrorCode.PARAM_ERROR,
                detail=f"Prompt 模板缺少变量：{', '.join(sorted(missing))}",
                status_code=400,
            )
        return template.format_map(_SafeFormatDict(params))

    def _missing_variables(self, template: str, params: dict[str, Any]) -> set[str]:
        names: set[str] = set()
        for _, field_name, _, _ in string.Formatter().parse(template):
            if field_name:
                names.add(field_name.split(".", 1)[0].split("[", 1)[0])
        return {name for name in names if name not in params}


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        raise KeyError(key)
