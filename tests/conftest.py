from collections.abc import AsyncIterator, Awaitable, Callable
from enum import Enum, StrEnum
from http import HTTPStatus
from typing import Final

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field, field_validator

from fastapi_custom_responses import (
    EXCEPTION_HANDLERS,
    ErrorCode,
    ErrorResponse,
    PaginatedResponse,
    Response,
    SuccessResponse,
    fastapi_responses,
)


class AccessErrorCode(ErrorCode):
    """Error codes for access failures, used to exercise consumer-defined codes."""

    PERMISSION_DENIED = "permission_denied"
    ACCOUNT_SUSPENDED = "account_suspended"


class StandaloneErrorCode(StrEnum):
    """Error codes declared without the library's base, as a consumer that cannot import it would."""

    MEMBERSHIP_REQUIRED = "membership_required"


class ValidationPayload(BaseModel):
    """Test model for validation error tests."""

    name: str
    age: int
    email: str


SAMPLE_PAYLOAD = ValidationPayload(name="Alice", age=30, email="alice@example.com")


class Color(str, Enum):
    """Test enum for enum validation tests."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class ConstrainedPayload(BaseModel):
    """Test model with field constraints for detailed error messages."""

    username: str = Field(..., min_length=3, max_length=20)
    score: int = Field(..., ge=0, le=100)
    rating: float = Field(..., gt=0, lt=5)
    color: Color
    tags: list[str] = Field(..., min_length=1, max_length=5)


class ValueErrorPayload(BaseModel):
    """Test model with a custom validator that raises ValueError."""

    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code format."""

        if not v.isdigit() or len(v) != 4:
            raise ValueError("Code must be exactly 4 digits")

        return v


RAISED_ERRORS: Final[dict[str, Exception]] = {
    "/error-response": ErrorResponse(error="Custom error message", status_code=HTTPStatus.BAD_REQUEST),
    "/error-response-not-found": ErrorResponse(error="Item not found", status_code=HTTPStatus.NOT_FOUND),
    "/error-response-with-code": ErrorResponse(
        error="Custom error message",
        status_code=HTTPStatus.FORBIDDEN,
        code=AccessErrorCode.PERMISSION_DENIED,
    ),
    "/error-response-from-status": ErrorResponse.from_status_code(HTTPStatus.FORBIDDEN),
    "/error-response-from-status-with-code": ErrorResponse.from_status_code(
        HTTPStatus.FORBIDDEN, code=AccessErrorCode.PERMISSION_DENIED
    ),
    "/http-exception": HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Not authenticated"),
    "/http-exception-unusual-status": HTTPException(
        status_code=HTTPStatus.IM_A_TEAPOT, detail="I'm a teapot"
    ),
    "/value-error": ValueError("Invalid value provided"),
    "/general-exception": RuntimeError("Something went wrong"),
}


def raise_error_endpoint(error: Exception) -> Callable[[], Awaitable[None]]:
    """Build an endpoint that raises the given error."""

    async def _raise_error() -> None:
        raise error

    return _raise_error


VALID_CONSTRAINED_PAYLOAD = ConstrainedPayload(
    username="alice", score=50, rating=2.5, color=Color.RED, tags=["a"]
)


def create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with exception handlers for testing."""

    app = FastAPI(exception_handlers=EXCEPTION_HANDLERS)

    @app.post("/validate")
    async def validate_endpoint(payload: ValidationPayload) -> dict:
        return {"success": True, "data": payload.model_dump()}

    @app.post("/validate-constrained")
    async def validate_constrained_endpoint(payload: ConstrainedPayload) -> dict:
        return {"success": True, "data": payload.model_dump()}

    @app.post("/validate-value-error")
    async def validate_value_error_endpoint(payload: ValueErrorPayload) -> dict:
        return {"success": True, "data": payload.model_dump()}

    @app.get("/response-with-data")
    async def response_with_data_endpoint() -> Response[ValidationPayload]:
        return Response(success=True, data=SAMPLE_PAYLOAD)

    @app.get("/success-response")
    async def success_response_endpoint() -> SuccessResponse:
        return SuccessResponse(success=True)

    @app.get("/paginated-response")
    async def paginated_response_endpoint() -> PaginatedResponse[ValidationPayload]:
        return PaginatedResponse.build_page([SAMPLE_PAYLOAD], offset=0, limit=10, total=1)

    for path, error in RAISED_ERRORS.items():
        app.get(path)(raise_error_endpoint(error))

    return app


def create_documented_app() -> FastAPI:
    """Create an app whose routes document their responses, for OpenAPI assertions."""

    app = FastAPI()

    @app.post(
        "/reports",
        responses=fastapi_responses(
            {
                HTTPStatus.CREATED: Response[ValidationPayload],
                HTTPStatus.FORBIDDEN: AccessErrorCode,
                HTTPStatus.NOT_FOUND: None,
            }
        ),
    )
    async def reports() -> SuccessResponse:
        return SuccessResponse(success=True)

    return app


@pytest.fixture
def documented_app() -> FastAPI:
    """App whose routes document their responses."""

    return create_documented_app()


@pytest.fixture
def app() -> FastAPI:
    """FastAPI app fixture."""

    return create_test_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the test app."""

    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
