from collections.abc import Mapping
from enum import StrEnum
from http import HTTPStatus
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class ErrorCode(Protocol):
    """An error code member that declares the HTTP status it is answered with."""

    @property
    def value(self) -> str:
        """The code's wire value."""

        raise NotImplementedError

    @property
    def status_code(self) -> HTTPStatus:
        """The HTTP status a response carrying this code has."""

        raise NotImplementedError


class DefaultErrorCode(StrEnum):
    """Codes for the conditions the library's own handlers detect."""

    VALIDATION_ERROR = "validation_error", HTTPStatus.BAD_REQUEST
    INVALID_VALUE = "invalid_value", HTTPStatus.BAD_REQUEST
    INTERNAL_ERROR = "internal_error", HTTPStatus.INTERNAL_SERVER_ERROR

    status_code: HTTPStatus

    def __new__(cls, value: str, status_code: HTTPStatus) -> Self:
        """Declare the wire value and HTTP status of one handler condition."""

        member = str.__new__(cls, value)
        member._value_ = value
        member.status_code = status_code

        return member


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
