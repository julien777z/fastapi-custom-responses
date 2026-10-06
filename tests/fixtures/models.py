from collections.abc import Callable
from enum import StrEnum
from http import HTTPStatus

from pydantic import BaseModel, Field, field_validator

from fastapi_custom_responses import ErrorResponseModel


class AccessErrorCode(StrEnum):
    """Error codes for access failures, used to exercise consumer-defined codes."""

    PERMISSION_DENIED = "permission_denied"
    ACCOUNT_SUSPENDED = "account_suspended"


class ValidationPayload(BaseModel):
    """Test model for validation error tests."""

    name: str
    age: int
    email: str


class Color(StrEnum):
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


class RaisedErrorCase(BaseModel):
    """One error a route raises and the envelope it must render."""

    build_exception: Callable[[], Exception]
    status_code: HTTPStatus
    expected_body: ErrorResponseModel


class ResponseMetadata(BaseModel):
    """Response documentation fixture values."""

    description: str
    explicit_refusal: str
    cancelled: str
    client_failures: str
    other_failures: str
    operation_id: str
