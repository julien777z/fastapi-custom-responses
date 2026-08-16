from collections.abc import AsyncIterator, Callable
from enum import Enum, StrEnum
from http import HTTPStatus
from typing import Final

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field, field_validator

from fastapi_custom_responses import (
    EXCEPTION_HANDLERS,
    ErrorResponse,
    PaginatedResponse,
    Response,
    SuccessResponse,
    fastapi_responses,
)


class AccessErrorCode(StrEnum):
    """Error codes for access failures, used to exercise consumer-defined codes."""

    PERMISSION_DENIED = "permission_denied"
    ACCOUNT_SUSPENDED = "account_suspended"


class ValidationPayload(BaseModel):
    """Test model for validation error tests."""

    name: str
    age: int
    email: str


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


SAMPLE_PAYLOAD = ValidationPayload(name="Alice", age=30, email="alice@example.com")

VALID_CONSTRAINED_PAYLOAD = ConstrainedPayload(
    username="alice", score=50, rating=2.5, color=Color.RED, tags=["a"]
)


class RaisedErrorCase(BaseModel):
    """One error a route raises and the envelope it must render."""

    build_error: Callable[[], Exception]
    status_code: HTTPStatus
    expected_body: dict


RAISED_ERROR_CASES: Final[dict[str, RaisedErrorCase]] = {
    "default_status": RaisedErrorCase(
        build_error=lambda: ErrorResponse("Custom error message"),
        status_code=HTTPStatus.BAD_REQUEST,
        expected_body={"success": False, "error": "Custom error message"},
    ),
    "custom_status": RaisedErrorCase(
        build_error=lambda: ErrorResponse("Item not found", HTTPStatus.NOT_FOUND),
        status_code=HTTPStatus.NOT_FOUND,
        expected_body={"success": False, "error": "Item not found"},
    ),
    "with_code": RaisedErrorCase(
        build_error=lambda: ErrorResponse(
            "Custom error message",
            HTTPStatus.FORBIDDEN,
            code=AccessErrorCode.PERMISSION_DENIED,
        ),
        status_code=HTTPStatus.FORBIDDEN,
        expected_body={
            "success": False,
            "error": "Custom error message",
            "code": "permission_denied",
        },
    ),
    "from_status_code": RaisedErrorCase(
        build_error=lambda: ErrorResponse.from_status_code(HTTPStatus.FORBIDDEN),
        status_code=HTTPStatus.FORBIDDEN,
        expected_body={
            "success": False,
            "error": "You don't have permission to perform this action",
        },
    ),
    "from_status_code_with_code": RaisedErrorCase(
        build_error=lambda: ErrorResponse.from_status_code(
            HTTPStatus.FORBIDDEN, code=AccessErrorCode.PERMISSION_DENIED
        ),
        status_code=HTTPStatus.FORBIDDEN,
        expected_body={
            "success": False,
            "error": "You don't have permission to perform this action",
            "code": "permission_denied",
        },
    ),
    "http_exception": RaisedErrorCase(
        build_error=lambda: HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Not authenticated"),
        status_code=HTTPStatus.UNAUTHORIZED,
        expected_body={"success": False, "error": "Not authenticated"},
    ),
    "http_exception_with_a_structured_detail": RaisedErrorCase(
        build_error=lambda: HTTPException(status_code=HTTPStatus.CONFLICT, detail={"reason": "taken"}),
        status_code=HTTPStatus.CONFLICT,
        expected_body={"success": False, "error": "{'reason': 'taken'}"},
    ),
    "value_error": RaisedErrorCase(
        build_error=lambda: ValueError("Invalid value provided"),
        status_code=HTTPStatus.BAD_REQUEST,
        expected_body={
            "success": False,
            "error": "Invalid value provided",
            "code": "invalid_value",
        },
    ),
    "unhandled_exception": RaisedErrorCase(
        build_error=lambda: RuntimeError("Something went wrong"),
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        expected_body={
            "success": False,
            "error": "An unexpected error occurred",
            "code": "internal_error",
        },
    ),
}


@pytest.fixture
def app() -> FastAPI:
    """Minimal FastAPI app with the library's exception handlers registered."""

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

    @app.get("/raise/{case_name}")
    async def raise_error_endpoint(case_name: str) -> None:
        raise RAISED_ERROR_CASES[case_name].build_error()

    return app


@pytest.fixture
def documented_app() -> FastAPI:
    """App whose routes document their responses."""

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
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the test app."""

    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
