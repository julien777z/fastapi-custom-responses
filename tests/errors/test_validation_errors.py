from http import HTTPStatus

import pytest
from httpx import AsyncClient
from pydantic import JsonValue

from fastapi_custom_responses import DefaultErrorCode
from tests.fixtures.models import Color
from tests.fixtures.responses import (
    SAMPLE_PAYLOAD,
    VALID_CONSTRAINED_PAYLOAD,
    VALUE_ERROR_PAYLOAD,
)


class TestValidationErrors:
    """Tests for request validation."""

    async def test_missing_field(self, client: AsyncClient) -> None:
        """Test that POST with missing required field returns 400 with human-readable message."""

        response = await client.post(
            "/validate",
            json={key: value for key, value in SAMPLE_PAYLOAD.model_dump().items() if key != "email"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": "Field 'email' is required",
            "code": DefaultErrorCode.VALIDATION_ERROR,
        }

    async def test_wrong_type(self, client: AsyncClient) -> None:
        """Test that POST with wrong type returns 400 with human-readable message."""

        response = await client.post("/validate", json={**SAMPLE_PAYLOAD.model_dump(), "age": "not-a-number"})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": "Field 'age' must be a valid integer",
            "code": DefaultErrorCode.VALIDATION_ERROR,
        }

    async def test_multiple_errors(self, client: AsyncClient) -> None:
        """Test that POST with multiple errors returns combined message."""

        response = await client.post(
            "/validate", json={**SAMPLE_PAYLOAD.model_dump(exclude={"age", "email"}), "name": 123}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": ("Field 'name' must be a string. Field 'age' is required. Field 'email' is required"),
            "code": DefaultErrorCode.VALIDATION_ERROR,
        }

    async def test_invalid_json(self, client: AsyncClient) -> None:
        """Test that POST with invalid JSON returns 400."""

        response = await client.post(
            "/validate", content="not valid json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST

        data = response.json()

        assert data["success"] is False

    async def test_valid_request_succeeds(self, client: AsyncClient) -> None:
        """Test that valid request succeeds."""

        response = await client.post("/validate", json=SAMPLE_PAYLOAD.model_dump())

        assert response.status_code == HTTPStatus.OK

        data = response.json()

        assert data["success"] is True

    @pytest.mark.parametrize(
        ("payload_override", "expected_error"),
        [
            ({"username": "ab"}, "Field 'username' must be at least 3 characters"),
            ({"username": "a" * 21}, "Field 'username' must be at most 20 characters"),
            ({"score": -1}, "Field 'score' must be at least 0"),
            ({"score": 101}, "Field 'score' must be at most 100"),
            ({"rating": 0}, "Field 'rating' must be greater than 0"),
            ({"rating": 5}, "Field 'rating' must be less than 5"),
            ({"tags": []}, "Field 'tags' must have at least 1 item"),
            ({"tags": ["a", "b", "c", "d", "e", "f"]}, "Field 'tags' must have at most 5 items"),
        ],
        ids=[
            "string_too_short",
            "string_too_long",
            "greater_than_equal",
            "less_than_equal",
            "greater_than",
            "less_than",
            "list_too_short",
            "list_too_long",
        ],
    )
    async def test_constrained_field_error(
        self, client: AsyncClient, payload_override: dict[str, JsonValue], expected_error: str
    ) -> None:
        """Test that constrained field violations produce specific error messages."""

        payload = {**VALID_CONSTRAINED_PAYLOAD.model_dump(mode="json"), **payload_override}

        response = await client.post("/validate-constrained", json=payload)

        assert response.status_code == HTTPStatus.BAD_REQUEST

        data = response.json()

        assert data["error"] == expected_error

    async def test_enum_includes_expected_values(self, client: AsyncClient) -> None:
        """Test that enum error includes the allowed values."""

        payload = {**VALID_CONSTRAINED_PAYLOAD.model_dump(mode="json"), "color": "purple"}

        response = await client.post("/validate-constrained", json=payload)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": f"Field 'color' must be one of: {Color.RED.value!r}, {Color.GREEN.value!r} or {Color.BLUE.value!r}",
            "code": DefaultErrorCode.VALIDATION_ERROR,
        }

    async def test_value_error_strips_pydantic_prefix(self, client: AsyncClient) -> None:
        """Test that value_error strips the 'Value error, ' prefix Pydantic adds."""

        response = await client.post(
            "/validate-value-error", json={**VALUE_ERROR_PAYLOAD.model_dump(), "code": "abc"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST

        data = response.json()

        assert data["error"] == "Code must be exactly 4 digits"

    async def test_valid_constrained_request_succeeds(self, client: AsyncClient) -> None:
        """Test that a valid request with all constraints met succeeds."""

        response = await client.post(
            "/validate-constrained", json=VALID_CONSTRAINED_PAYLOAD.model_dump(mode="json")
        )

        assert response.status_code == HTTPStatus.OK

        data = response.json()

        assert data["success"] is True
