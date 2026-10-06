import logging
from collections.abc import Callable, Mapping
from enum import StrEnum
from http import HTTPStatus
from typing import Final, Literal, Self

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from pydantic_core import ErrorDetails
from starlette.exceptions import HTTPException

from fastapi_custom_responses.models.errors import (
    ConstraintRule,
    DefaultErrorCode,
    ErrorResponseModel,
)

logger: logging.Logger = logging.getLogger(__name__)

SIMPLE_TYPE_MESSAGES: Final[dict[str, str]] = {
    "missing": "is required",
    "string_type": "must be a string",
    "int_type": "must be a valid integer",
    "int_parsing": "must be a valid integer",
    "float_type": "must be a valid number",
    "float_parsing": "must be a valid number",
    "bool_type": "must be a boolean",
    "bool_parsing": "must be a boolean",
    "uuid_type": "must be a valid UUID",
    "uuid_parsing": "must be a valid UUID",
}


CONSTRAINT_RULES: Final[dict[str, ConstraintRule]] = {
    "string_too_short": ConstraintRule(
        ctx_key="min_length", template="must be at least {value} characters", fallback="is too short"
    ),
    "string_too_long": ConstraintRule(
        ctx_key="max_length", template="must be at most {value} characters", fallback="is too long"
    ),
    "too_short": ConstraintRule(
        ctx_key="min_length",
        template="must have at least {value} {unit}",
        fallback="has too few items",
    ),
    "too_long": ConstraintRule(
        ctx_key="max_length",
        template="must have at most {value} {unit}",
        fallback="has too many items",
    ),
    "greater_than": ConstraintRule(
        ctx_key="gt", template="must be greater than {value}", fallback="has an invalid value"
    ),
    "greater_than_equal": ConstraintRule(
        ctx_key="ge", template="must be at least {value}", fallback="has an invalid value"
    ),
    "less_than": ConstraintRule(
        ctx_key="lt", template="must be less than {value}", fallback="has an invalid value"
    ),
    "less_than_equal": ConstraintRule(
        ctx_key="le", template="must be at most {value}", fallback="has an invalid value"
    ),
    "enum": ConstraintRule(
        ctx_key="expected", template="must be one of: {value}", fallback="has an invalid value"
    ),
}


EXCEPTION_RESPONSES: Final[dict[int | str, dict[Literal["model"], type[BaseModel]]]] = {
    "4XX": {"model": ErrorResponseModel},
    "5XX": {"model": ErrorResponseModel},
    HTTPStatus.BAD_REQUEST: {
        "model": ErrorResponseModel[
            Literal[DefaultErrorCode.VALIDATION_ERROR, DefaultErrorCode.INVALID_VALUE]
        ]
    },
    HTTPStatus.INTERNAL_SERVER_ERROR: {"model": ErrorResponseModel[Literal[DefaultErrorCode.INTERNAL_ERROR]]},
}


class ErrorResponse(Exception):
    """Normalized application error."""

    def __init__(
        self,
        error: str,
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
        *,
        code: StrEnum | None = None,
    ) -> None:
        """Application error fields."""

        self.error = error
        self.status_code = status_code
        self.code = code

        super().__init__(error)

    @classmethod
    def from_status_code(cls, status_code: HTTPStatus, *, code: StrEnum | None = None) -> Self:
        """Application error with a standard status phrase."""

        return cls(error=status_code.phrase, status_code=status_code, code=code)


def format_field_location(loc: tuple[int | str, ...]) -> str:
    """Validation field location."""

    field_loc = loc[1:] if loc and loc[0] in ("body", "query", "path", "header") else loc
    field_parts = [str(part) for part in field_loc]

    if not field_parts:
        return str(loc[-1]) if loc else "field"

    return ".".join(field_parts)


def format_single_error(error: ErrorDetails) -> str:
    """Validation error message."""

    field = format_field_location(error["loc"])
    error_type = error["type"]
    msg = error["msg"]
    ctx = error.get("ctx", {})

    if error_type in SIMPLE_TYPE_MESSAGES:
        return f"Field '{field}' {SIMPLE_TYPE_MESSAGES[error_type]}"

    rule = CONSTRAINT_RULES.get(error_type)

    if rule is not None:
        return rule.format_error(field, ctx)

    match error_type:
        case "value_error":
            # Pydantic prefixes with "Value error, " -- strip it
            return msg.removeprefix("Value error, ")
        case "json_invalid":
            return "Invalid JSON in request body"
        case _:
            if msg:
                return f"Field '{field}': {msg}"

            return f"Field '{field}' is invalid"


def format_validation_errors(exc: RequestValidationError) -> str:
    """Combined validation errors."""

    errors = exc.errors()

    if not errors:
        return HTTPStatus.BAD_REQUEST.phrase

    return ". ".join(format_single_error(error) for error in errors)


def error_json_response(
    status_code: int, error: str, code: str | None, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    """Normalized error JSON response."""

    response = ErrorResponseModel(success=False, error=error, code=code)

    content = response.model_dump(mode="json", exclude_none=True)

    return JSONResponse(status_code=status_code, content=content, headers=headers)


def exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """FastAPI exception callback."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error = HTTPStatus.INTERNAL_SERVER_ERROR.phrase
    code: str | None = DefaultErrorCode.INTERNAL_ERROR
    headers: Mapping[str, str] | None = None

    match exc:
        case RequestValidationError():
            logger.warning("Validation error: %s", exc.errors())

            status_code = HTTPStatus.BAD_REQUEST
            error = format_validation_errors(exc)
            code = DefaultErrorCode.VALIDATION_ERROR
        case ErrorResponse():
            logger.info("ErrorResponse: %s - %s", exc.status_code, exc.error)

            status_code = exc.status_code
            error = exc.error
            code = exc.code
        case HTTPException():
            status_code = exc.status_code
            error = str(exc.detail)
            code = None
            headers = exc.headers
        case ValueError() if not isinstance(exc, ValidationError):
            logger.exception(exc)

            status_code = HTTPStatus.BAD_REQUEST
            error = str(exc)
            code = DefaultErrorCode.INVALID_VALUE
        case _:
            logger.exception(exc)

    return error_json_response(status_code, error, code, headers=headers)


EXCEPTION_HANDLERS: Final[dict[type[Exception], Callable[[Request, Exception], JSONResponse]]] = {
    exception_type: exception_handler
    for exception_type in (
        HTTPException,
        RequestValidationError,
        ValidationError,
        ValueError,
        ErrorResponse,
        Exception,
    )
}
