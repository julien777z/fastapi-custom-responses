from http import HTTPStatus

from httpx import AsyncClient


class TestValidationErrors:
    """Tests for Pydantic validation error handling."""

    async def test_validation_error_missing_field(self, client: AsyncClient) -> None:
        """Test that POST with missing required field returns 400 with human-readable message."""

        response = await client.post("/validate", json={"name": "John", "age": 30})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": "Field 'email' is required",
            "code": "validation_error",
        }

    async def test_validation_error_wrong_type(self, client: AsyncClient) -> None:
        """Test that POST with wrong type returns 400 with human-readable message."""

        response = await client.post(
            "/validate", json={"name": "John", "age": "not-a-number", "email": "test@example.com"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": "Field 'age' must be a valid integer",
            "code": "validation_error",
        }

    async def test_validation_error_multiple_errors(self, client: AsyncClient) -> None:
        """Test that POST with multiple errors returns combined message."""

        response = await client.post("/validate", json={"name": 123})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": ("Field 'name' must be a string. Field 'age' is required. Field 'email' is required"),
            "code": "validation_error",
        }

    async def test_validation_error_invalid_json(self, client: AsyncClient) -> None:
        """Test that POST with invalid JSON returns 400."""

        response = await client.post(
            "/validate", content="not valid json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["success"] is False

    async def test_valid_request_succeeds(self, client: AsyncClient) -> None:
        """Test that valid request succeeds."""

        response = await client.post(
            "/validate", json={"name": "John", "age": 30, "email": "john@example.com"}
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["success"] is True
