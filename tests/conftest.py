import asyncio
from enum import Enum
from http import HTTPStatus

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field, field_validator

from fastapi_custom_responses import EXCEPTION_HANDLERS, ErrorResponse


class _TestPayload(BaseModel):
    """Test model for validation error tests."""

    name: str
    age: int
    email: str


class _Color(str, Enum):
    """Test enum for enum validation tests."""

    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class _ConstrainedPayload(BaseModel):
    """Test model with field constraints for detailed error messages."""

    username: str = Field(..., min_length=3, max_length=20)
    score: int = Field(..., ge=0, le=100)
    rating: float = Field(..., gt=0, lt=5)
    color: _Color
    tags: list[str] = Field(..., min_length=1, max_length=5)


class _ValueErrorPayload(BaseModel):
    """Test model with a custom validator that raises ValueError."""

    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code format."""

        if not v.isdigit() or len(v) != 4:
            raise ValueError("Code must be exactly 4 digits")

        return v


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with exception handlers for testing."""

    app = FastAPI(exception_handlers=EXCEPTION_HANDLERS)

    @app.post("/validate")
    async def validate_endpoint(payload: _TestPayload) -> dict:
        return {"success": True, "data": payload.model_dump()}

    @app.post("/validate-constrained")
    async def validate_constrained_endpoint(payload: _ConstrainedPayload) -> dict:
        return {"success": True, "data": payload.model_dump()}

    @app.post("/validate-value-error")
    async def validate_value_error_endpoint(payload: _ValueErrorPayload) -> dict:
        return {"success": True, "data": payload.model_dump()}

    @app.get("/error-response")
    async def error_response_endpoint() -> dict:
        raise ErrorResponse(error="Custom error message", status_code=HTTPStatus.BAD_REQUEST)

    @app.get("/error-response-not-found")
    async def error_response_not_found_endpoint() -> dict:
        raise ErrorResponse(error="Item not found", status_code=HTTPStatus.NOT_FOUND)

    @app.get("/error-response-from-status")
    async def error_response_from_status_endpoint() -> dict:
        raise ErrorResponse.from_status_code(HTTPStatus.FORBIDDEN)

    @app.get("/http-exception")
    async def http_exception_endpoint() -> dict:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Not authenticated")

    @app.get("/value-error")
    async def value_error_endpoint() -> dict:
        raise ValueError("Invalid value provided")

    @app.get("/general-exception")
    async def general_exception_endpoint() -> dict:
        raise RuntimeError("Something went wrong")

    return app


@pytest.fixture
def app() -> FastAPI:
    """FastAPI app fixture."""

    return _create_test_app()


@pytest.fixture(autouse=True)
async def client(request, app: FastAPI) -> AsyncClient | None:
    """Async HTTP client fixture that auto-injects into test classes."""

    # Skip for sync tests
    if not asyncio.iscoroutinefunction(request.node.obj):
        yield None
        return

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        if request.instance is not None:
            request.instance.client = client

        yield client
