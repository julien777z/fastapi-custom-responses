import logging
from http import HTTPStatus
from typing import Callable

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from fastapi_custom_responses.responses import Response

logger = logging.getLogger(__name__)

ERROR_MESSAGES: dict[int, str] = {
    HTTPStatus.UNAUTHORIZED: "Authentication required",
    HTTPStatus.FORBIDDEN: "You don't have permission to perform this action",
    HTTPStatus.NOT_FOUND: "Resource not found",
    HTTPStatus.BAD_REQUEST: "Invalid request",
    HTTPStatus.INTERNAL_SERVER_ERROR: "An unexpected error occurred",
}


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


def _validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors from pydantic models."""

    logger.exception(exc)

    response = Response(success=False, error=ERROR_MESSAGES[HTTPStatus.BAD_REQUEST])

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


EXCEPTION_HANDLERS: dict[type[Exception], Callable[[Request, Exception], JSONResponse]] = {
    RequestValidationError: _validation_exception_handler,
    ErrorResponse: _error_response_handler,
    Exception: _general_exception_handler,
}
