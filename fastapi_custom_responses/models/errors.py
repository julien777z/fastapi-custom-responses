from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class DefaultErrorCode(StrEnum):
    """Codes for the conditions the library's own handlers detect."""

    VALIDATION_ERROR = "validation_error"
    INVALID_VALUE = "invalid_value"
    INTERNAL_ERROR = "internal_error"


class ErrorResponseModel[CodeT: str](BaseModel):
    """Error response envelope."""

    success: Literal[False]
    error: str
    code: CodeT | None = None


class ConstraintRule(BaseModel):
    """Constraint message rule."""

    ctx_key: str
    template: str
    fallback: str

    def format_error(self, field: str, ctx: Mapping[str, object]) -> str:
        """Human-readable constraint violation."""

        value = ctx.get(self.ctx_key)

        if value is None:
            return f"Field '{field}' {self.fallback}"

        if isinstance(value, float) and value.is_integer():
            value = int(value)

        unit = "item" if value == 1 else "items"

        return f"Field '{field}' {self.template.format(value=value, unit=unit)}"
