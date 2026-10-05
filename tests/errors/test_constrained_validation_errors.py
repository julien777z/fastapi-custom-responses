from http import HTTPStatus
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import (
    VALID_CONSTRAINED_PAYLOAD,
)


class TestConstrainedValidationErrors:
    """Tests for constraint-aware validation error messages."""

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
        self, client: AsyncClient, payload_override: dict[str, Any], expected_error: str
    ) -> None:
        """Test that constrained field violations produce specific error messages."""

        payload = {**VALID_CONSTRAINED_PAYLOAD, **payload_override}
        response = await client.post("/validate-constrained", json=payload)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == expected_error

    async def test_enum_includes_expected_values(self, client: AsyncClient) -> None:
        """Test that enum error includes the allowed values."""

        payload = {**VALID_CONSTRAINED_PAYLOAD, "color": "purple"}
        response = await client.post("/validate-constrained", json=payload)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": "Field 'color' must be one of: 'red', 'green' or 'blue'",
            "code": "validation_error",
        }

    async def test_value_error_strips_pydantic_prefix(self, client: AsyncClient) -> None:
        """Test that value_error strips the 'Value error, ' prefix Pydantic adds."""

        response = await client.post("/validate-value-error", json={"code": "abc"})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Code must be exactly 4 digits"

    async def test_valid_constrained_request_succeeds(self, client: AsyncClient) -> None:
        """Test that a valid request with all constraints met succeeds."""

        response = await client.post("/validate-constrained", json=VALID_CONSTRAINED_PAYLOAD)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["success"] is True
