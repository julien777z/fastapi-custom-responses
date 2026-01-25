from http import HTTPStatus

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from fastapi_custom_responses import EXCEPTION_HANDLERS, ErrorResponse


class _TestPayload(BaseModel):
    """Test model for validation error tests."""

    name: str
    age: int
    email: str


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with exception handlers for testing."""

    app = FastAPI(exception_handlers=EXCEPTION_HANDLERS)

    @app.post("/validate")
    async def validate_endpoint(payload: _TestPayload) -> dict:
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

    import asyncio

    # Skip for sync tests
    if not asyncio.iscoroutinefunction(request.node.obj):
        yield None
        return

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        if request.instance is not None:
            request.instance.client = client

        yield client
