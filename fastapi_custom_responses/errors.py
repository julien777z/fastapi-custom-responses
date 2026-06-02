import logging
from collections.abc import Callable
from http import HTTPStatus
from typing import Final, Self

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fastapi_custom_responses.responses import Response

logger = logging.getLogger(__name__)

ERROR_MESSAGES: Final[dict[int, str]] = {
    HTTPStatus.UNAUTHORIZED: "Authentication required",
    HTTPStatus.FORBIDDEN: "You don't have permission to perform this action",
    HTTPStatus.NOT_FOUND: "Resource not found",
    HTTPStatus.BAD_REQUEST: "Invalid request",
    HTTPStatus.INTERNAL_SERVER_ERROR: "An unexpected error occurred",
}

SIMPLE_TYPE_MESSAGES: Final[dict[str, str]] = {
    "missing": "is required",
    "string_type": "must be a string",
    "str_type": "must be a string",
    "int_type": "must be a valid integer",
    "int_parsing": "must be a valid integer",
    "float_type": "must be a valid number",
    "float_parsing": "must be a valid number",
    "bool_type": "must be a boolean",
    "bool_parsing": "must be a boolean",
    "uuid_type": "must be a valid UUID",
    "uuid_parsing": "must be a valid UUID",
}


class ErrorResponseModel(BaseModel):
    """Pydantic model for error response schema. Use this in FastAPI's `responses` parameter to document the error response schema."""

    success: bool
    error: str


class ErrorResponse(Exception):
    """Standard error response that includes error message."""

    def __init__(self, error: str, status_code: int = HTTPStatus.BAD_REQUEST) -> None:
        """Initialize error response with message and status code."""

        self.error = error
        self.status_code = status_code

        super().__init__(error)

    @classmethod
    def from_status_code(cls, status_code: int) -> Self:
        """Create an error response from a status code."""

        return cls(
            error=ERROR_MESSAGES.get(status_code, ERROR_MESSAGES[HTTPStatus.INTERNAL_SERVER_ERROR]),
            status_code=status_code,
        )


def format_field_location(loc: tuple[int | str, ...]) -> str:
    """Extract the field name from a validation error location tuple."""

    # Filter out 'body', 'query', 'path' prefixes and join remaining parts
    field_parts = [str(part) for part in loc if part not in ("body", "query", "path", "header")]

    if not field_parts:
        # If all parts were filtered out, use the last part of the original location
        return str(loc[-1]) if loc else "field"

    return ".".join(field_parts)


def format_number(value: int | float) -> str:
    """Format a numeric constraint value for display, stripping unnecessary '.0' from whole floats."""

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
}


def format_constraint_error(field: str, ctx: dict, rule: ConstraintRule) -> str:
    """Format a constraint violation from its rule, falling back when the bound is absent from ctx."""

    value = ctx.get(rule.ctx_key)
    if value is None:
        return f"Field '{field}' {rule.fallback}"

    unit = "item" if value == 1 else "items"

    return f"Field '{field}' {rule.template.format(value=format_number(value), unit=unit)}"


def format_single_error(error: dict) -> str:
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
        case "enum":
            expected = ctx.get("expected", "")
            if expected:
                return f"Field '{field}' must be one of: {expected}"
            return f"Field '{field}' has an invalid value"
        case "value_error":
            # Pydantic prefixes with "Value error, " -- strip it
            return msg.removeprefix("Value error, ")
        case "json_invalid":
            return "Invalid JSON in request body"
        case _:
            # For any other error type, use the Pydantic message with the field name
            if msg:
                return f"Field '{field}': {msg}"

            return f"Field '{field}' is invalid"


def format_validation_errors(exc: RequestValidationError) -> str:
    """Format all validation errors into a single human-readable message."""

    errors = exc.errors()

    if not errors:
        return ERROR_MESSAGES[HTTPStatus.BAD_REQUEST]

    return ". ".join(format_single_error(error) for error in errors)


def error_json_response(status_code: int, error: str) -> JSONResponse:
    """Build the standard `{success: false, error: ...}` JSON response."""

    response = Response(success=False, error=error)

    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))


def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors from pydantic models with human-readable messages."""

    logger.warning("Validation error: %s", exc.errors())

    return error_json_response(HTTPStatus.BAD_REQUEST, format_validation_errors(exc))


def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    """Handle value errors, e.g., Pydantic validation errors."""

    logger.exception(exc)

    return error_json_response(HTTPStatus.BAD_REQUEST, str(exc))


def error_response_handler(_: Request, exc: ErrorResponse) -> JSONResponse:
    """Convert ErrorResponse exceptions to proper JSONResponse objects."""

    logger.info("ErrorResponse: %s - %s", exc.status_code, exc.error)

    return error_json_response(exc.status_code, exc.error)


def general_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""

    logger.exception(exc)

    return error_json_response(
        HTTPStatus.INTERNAL_SERVER_ERROR, ERROR_MESSAGES[HTTPStatus.INTERNAL_SERVER_ERROR]
    )


def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Convert HTTPException to our standard error format."""

    error_message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    return error_json_response(exc.status_code, error_message)


EXCEPTION_HANDLERS: dict[type[Exception], Callable[[Request, Exception], JSONResponse]] = {
    HTTPException: http_exception_handler,
    RequestValidationError: validation_exception_handler,
    ValueError: value_error_handler,
    ErrorResponse: error_response_handler,
    Exception: general_exception_handler,
}
