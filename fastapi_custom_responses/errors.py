import logging
from collections.abc import Callable, Mapping
from enum import StrEnum
from http import HTTPStatus
from types import UnionType
from typing import Any, Final, Literal, Self

from fastapi import Request
from fastapi.exceptions import RequestValidationError, StarletteHTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

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

type ResponseSpec = type[StrEnum] | type[BaseModel] | UnionType | None


class DefaultErrorCode(StrEnum):
    """Codes for the conditions the library's own handlers detect."""

    VALIDATION_ERROR = "validation_error"
    INVALID_VALUE = "invalid_value"
    INTERNAL_ERROR = "internal_error"


class ErrorResponseModel[CodeT: str](BaseModel):
    """Body every error response carries, and the schema documenting it in OpenAPI."""

    success: Literal[False]
    error: str
    code: CodeT | None = None


class ErrorResponse(Exception):
    """Exception carrying the message, status code, and code to render as an error response."""

    def __init__(
        self,
        error: str,
        status_code: HTTPStatus = HTTPStatus.BAD_REQUEST,
        *,
        code: StrEnum | None = None,
    ) -> None:
        """Initialize error response with message, status code, and error code."""

        self.error = error
        self.status_code = status_code
        self.code = code

        super().__init__(error)

    @classmethod
    def from_status_code(cls, status_code: HTTPStatus, *, code: StrEnum | None = None) -> Self:
        """Create an error response carrying the standard phrase for a status code."""

        return cls(error=status_code.phrase, status_code=status_code, code=code)


def format_field_location(loc: tuple[int | str, ...]) -> str:
    """Extract the field name from a validation error location tuple."""

    field_parts = [str(part) for part in loc if part not in ("body", "query", "path", "header")]

    if not field_parts:
        return str(loc[-1]) if loc else "field"

    return ".".join(field_parts)


def format_constraint_value(value: int | float | str) -> str:
    """Format a constraint value for display, stripping unnecessary '.0' from whole floats."""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)


class ConstraintRule(BaseModel):
    """Maps a Pydantic constraint error type to its `ctx` key, message template, and fallback."""

    ctx_key: str
    template: str
    fallback: str


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


def format_constraint_error(field: str, ctx: dict[str, Any], rule: ConstraintRule) -> str:
    """Format a constraint violation from its rule, falling back when the bound is absent from ctx."""

    value = ctx.get(rule.ctx_key)
    if value is None:
        return f"Field '{field}' {rule.fallback}"

    unit = "item" if value == 1 else "items"

    return f"Field '{field}' {rule.template.format(value=format_constraint_value(value), unit=unit)}"


def format_single_error(error: dict[str, Any]) -> str:
    """Format a single Pydantic validation error into a human-readable message."""

    field = format_field_location(error.get("loc", ()))
    error_type = error.get("type", "")
    msg = error.get("msg", "")
    ctx = error.get("ctx", {})

    if error_type in SIMPLE_TYPE_MESSAGES:
        return f"Field '{field}' {SIMPLE_TYPE_MESSAGES[error_type]}"

    rule = CONSTRAINT_RULES.get(error_type)
    if rule is not None:
        return format_constraint_error(field, ctx, rule)

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
    """Format all validation errors into a single human-readable message."""

    errors = exc.errors()

    if not errors:
        return HTTPStatus.BAD_REQUEST.phrase

    return ". ".join(format_single_error(error) for error in errors)


def error_json_response(
    status_code: int, error: str, code: str | None, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    """Build the standard `{success: false, error: ..., code: ...}` response, carrying any given headers."""

    response = ErrorResponseModel(success=False, error=error, code=code)
    content = response.model_dump(mode="json", exclude_none=True)

    return JSONResponse(status_code=status_code, content=content, headers=headers)


def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors from pydantic models with human-readable messages."""

    logger.warning("Validation error: %s", exc.errors())

    return error_json_response(
        HTTPStatus.BAD_REQUEST, format_validation_errors(exc), DefaultErrorCode.VALIDATION_ERROR
    )


def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    """Handle a value the application rejected, reporting it as a bad request."""

    logger.exception(exc)

    return error_json_response(HTTPStatus.BAD_REQUEST, str(exc), DefaultErrorCode.INVALID_VALUE)


def error_response_handler(_: Request, exc: ErrorResponse) -> JSONResponse:
    """Render an error the application raised deliberately, carrying the code it named."""

    logger.info("ErrorResponse: %s - %s", exc.status_code, exc.error)

    return error_json_response(exc.status_code, exc.error, exc.code)


def general_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Report a fault the application did not handle, keeping its detail out of the body."""

    logger.exception(exc)

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR

    return error_json_response(status_code, status_code.phrase, DefaultErrorCode.INTERNAL_ERROR)


def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Convert an HTTP exception, including one the router raises, to the error envelope."""

    return error_json_response(exc.status_code, str(exc.detail), None, headers=exc.headers)


def documented_model(spec: ResponseSpec) -> type[BaseModel]:
    """Return the model documenting one response: the given model, or the error envelope."""

    if isinstance(spec, type) and issubclass(spec, BaseModel):
        return spec

    return ErrorResponseModel if spec is None else ErrorResponseModel[spec]


def fastapi_responses(specs: dict[HTTPStatus, ResponseSpec]) -> dict[int | str, dict[str, Any]]:
    """Build FastAPI's `responses` mapping from status codes and their models or error codes."""

    return {status_code: {"model": documented_model(spec)} for status_code, spec in specs.items()}


EXCEPTION_HANDLERS: dict[type[Exception], Callable[[Request, Exception], JSONResponse]] = {
    StarletteHTTPException: http_exception_handler,
    RequestValidationError: validation_exception_handler,
    ValidationError: general_exception_handler,
    ValueError: value_error_handler,
    ErrorResponse: error_response_handler,
    Exception: general_exception_handler,
}
