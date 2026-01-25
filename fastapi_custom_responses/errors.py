import logging
from http import HTTPStatus
from typing import Callable

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fastapi_custom_responses.responses import Response

logger = logging.getLogger(__name__)

ERROR_MESSAGES: dict[int, str] = {
    HTTPStatus.UNAUTHORIZED: "Authentication required",
    HTTPStatus.FORBIDDEN: "You don't have permission to perform this action",
    HTTPStatus.NOT_FOUND: "Resource not found",
    HTTPStatus.BAD_REQUEST: "Invalid request",
    HTTPStatus.INTERNAL_SERVER_ERROR: "An unexpected error occurred",
}


class ErrorResponseModel(BaseModel):
    """Pydantic model for error response schema. Use this in FastAPI's `responses` parameter to document the error response schema."""

    success: bool
    error: str


class ErrorResponse(Exception):
    """Standard error response that includes error message."""

    def __init__(self, error: str, status_code: int = HTTPStatus.BAD_REQUEST) -> None:
        """Initialize error response with message and status code.

        Args:
            error: Error message to return
            status_code: HTTP status code for the response
        """

        self.error = error
        self.status_code = status_code

        super().__init__(error)

    @classmethod
    def from_status_code(cls, status_code: int) -> "ErrorResponse":
        """Create an error response from a status code.

        Args:
            status_code: HTTP status code to get error message for

        Returns:
            ErrorResponse with the appropriate error message for the status code
        """

        return cls(
            error=ERROR_MESSAGES.get(status_code, ERROR_MESSAGES[HTTPStatus.INTERNAL_SERVER_ERROR]),
            status_code=status_code,
        )


def _format_field_location(loc: tuple) -> str:
    """Extract the field name from a validation error location tuple.

    Args:
        loc: Location tuple from Pydantic error (e.g., ('body', 'email') or ('query', 'page'))

    Returns:
        Human-readable field name (e.g., 'email' or 'page')
    """

    # Filter out 'body', 'query', 'path' prefixes and join remaining parts
    field_parts = [str(part) for part in loc if part not in ("body", "query", "path", "header")]

    if not field_parts:
        # If all parts were filtered out, use the last part of the original location
        return str(loc[-1]) if loc else "field"

    return ".".join(field_parts)


def _format_single_error(error: dict) -> str:
    """Format a single Pydantic validation error into a human-readable message.

    Args:
        error: A single error dict from RequestValidationError.errors()

    Returns:
        Human-readable error message
    """

    field = _format_field_location(error.get("loc", ()))
    error_type = error.get("type", "")
    msg = error.get("msg", "")

    # Map common Pydantic error types to human-readable messages
    match error_type:
        case "missing":
            return f"Field '{field}' is required"
        case "string_type" | "str_type":
            return f"Field '{field}' must be a string"
        case "int_type" | "int_parsing":
            return f"Field '{field}' must be a valid integer"
        case "float_type" | "float_parsing":
            return f"Field '{field}' must be a valid number"
        case "bool_type" | "bool_parsing":
            return f"Field '{field}' must be a boolean"
        case "enum":
            return f"Field '{field}' has an invalid value"
        case "uuid_type" | "uuid_parsing":
            return f"Field '{field}' must be a valid UUID"
        case "string_too_short":
            return f"Field '{field}' is too short"
        case "string_too_long":
            return f"Field '{field}' is too long"
        case "greater_than" | "greater_than_equal" | "less_than" | "less_than_equal":
            return f"Field '{field}' has an invalid value: {msg}"
        case "value_error":
            # Use the message directly for value errors as they're typically already human-readable
            return f"Field '{field}': {msg}"
        case "json_invalid":
            return "Invalid JSON in request body"
        case _:
            # For any other error type, use the Pydantic message with the field name
            if msg:
                return f"Field '{field}': {msg}"

            return f"Field '{field}' is invalid"


def _format_validation_errors(exc: RequestValidationError) -> str:
    """Format all validation errors from a RequestValidationError into a human-readable message.

    Args:
        exc: The RequestValidationError exception

    Returns:
        Human-readable error message combining all validation errors
    """

    errors = exc.errors()

    if not errors:
        return ERROR_MESSAGES[HTTPStatus.BAD_REQUEST]

    if len(errors) == 1:
        return _format_single_error(errors[0])

    # Multiple errors: combine them with periods
    formatted_errors = [_format_single_error(error) for error in errors]

    return ". ".join(formatted_errors)


def _validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors from pydantic models with human-readable messages."""

    logger.warning("Validation error: %s", exc.errors())

    error_message = _format_validation_errors(exc)
    response = Response(success=False, error=error_message)

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(mode="json"),
    )


def _value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    """Handle value errors, e.g., Pydantic validation errors."""

    logger.exception(exc)

    response = Response(success=False, error=str(exc))

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(mode="json"),
    )


def _error_response_handler(_: Request, exc: ErrorResponse) -> JSONResponse:
    """Convert ErrorResponse exceptions to proper JSONResponse objects."""

    logger.info("ErrorResponse: %s - %s", exc.status_code, exc.error)

    response = Response(success=False, error=exc.error)

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(mode="json"),
    )


def _general_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""

    logger.exception(exc)

    response = Response(success=False, error=ERROR_MESSAGES[HTTPStatus.INTERNAL_SERVER_ERROR])

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(mode="json"),
    )


def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Convert HTTPException to our standard error format."""

    error_message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    response = Response(success=False, error=error_message)

    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(mode="json"),
    )


EXCEPTION_HANDLERS: dict[type[Exception], Callable[[Request, Exception], JSONResponse]] = {
    HTTPException: _http_exception_handler,
    RequestValidationError: _validation_exception_handler,
    ValueError: _value_error_handler,
    ErrorResponse: _error_response_handler,
    Exception: _general_exception_handler,
}
