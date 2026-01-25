from http import HTTPStatus

from httpx import AsyncClient
import pytest

from fastapi_custom_responses.errors import _format_field_location, _format_single_error


class TestValidationErrors:
    """Tests for Pydantic validation error handling."""

    client: AsyncClient

    @pytest.mark.asyncio
    async def test_validation_error_missing_field(self) -> None:
        """Test that POST with missing required field returns 400 with human-readable message."""

        response = await self.client.post("/validate", json={"name": "John", "age": 30})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert "email" in data["error"]
        assert "required" in data["error"]

    @pytest.mark.asyncio
    async def test_validation_error_wrong_type(self) -> None:
        """Test that POST with wrong type returns 400 with human-readable message."""

        response = await self.client.post(
            "/validate", json={"name": "John", "age": "not-a-number", "email": "test@example.com"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert "age" in data["error"]
        assert "integer" in data["error"]

    @pytest.mark.asyncio
    async def test_validation_error_multiple_errors(self) -> None:
        """Test that POST with multiple errors returns combined message."""

        response = await self.client.post("/validate", json={"name": 123})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        # Should mention multiple fields
        assert "age" in data["error"] or "email" in data["error"]

    @pytest.mark.asyncio
    async def test_validation_error_invalid_json(self) -> None:
        """Test that POST with invalid JSON returns 400."""

        response = await self.client.post(
            "/validate", content="not valid json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_valid_request_succeeds(self) -> None:
        """Test that valid request succeeds."""

        response = await self.client.post(
            "/validate", json={"name": "John", "age": 30, "email": "john@example.com"}
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["success"] is True


class TestErrorResponse:
    """Tests for ErrorResponse exception handling."""

    client: AsyncClient

    @pytest.mark.asyncio
    async def test_error_response_custom_message(self) -> None:
        """Test that raising ErrorResponse returns custom message."""

        response = await self.client.get("/error-response")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Custom error message"

    @pytest.mark.asyncio
    async def test_error_response_custom_status_code(self) -> None:
        """Test that ErrorResponse can use different status codes."""

        response = await self.client.get("/error-response-not-found")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Item not found"

    @pytest.mark.asyncio
    async def test_error_response_from_status_code(self) -> None:
        """Test that ErrorResponse.from_status_code() uses predefined messages."""

        response = await self.client.get("/error-response-from-status")

        assert response.status_code == HTTPStatus.FORBIDDEN
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "You don't have permission to perform this action"


class TestHTTPExceptionHandler:
    """Tests for HTTPException handling."""

    client: AsyncClient

    @pytest.mark.asyncio
    async def test_http_exception_handler(self) -> None:
        """Test that HTTPException is formatted correctly."""

        response = await self.client.get("/http-exception")

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Not authenticated"


class TestValueErrorHandler:
    """Tests for ValueError handling."""

    client: AsyncClient

    @pytest.mark.asyncio
    async def test_value_error_handler(self) -> None:
        """Test that ValueError returns str(exc)."""

        response = await self.client.get("/value-error")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Invalid value provided"


class TestGeneralExceptionHandler:
    """Tests for unhandled exception handling."""

    client: AsyncClient

    @pytest.mark.asyncio
    async def test_general_exception_handler(self) -> None:
        """Test that unhandled exceptions return generic 500 message.

        Note: In test environments, FastAPI may re-raise exceptions instead of
        returning the error response. This test verifies either behavior.
        """

        try:
            response = await self.client.get("/general-exception")
            # If we get a response, verify it's a 500 error
            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "An unexpected error occurred"
        except RuntimeError as e:
            # In test mode, the exception may be re-raised
            assert str(e) == "Something went wrong"


class TestFormatValidationErrors:
    """Unit tests for the _format_validation_errors helper functions."""

    def test_format_field_location_simple(self) -> None:
        """Test that simple field location is formatted correctly."""

        assert _format_field_location(("body", "email")) == "email"
        assert _format_field_location(("query", "page")) == "page"
        assert _format_field_location(("path", "id")) == "id"

    def test_format_field_location_nested(self) -> None:
        """Test that nested field location is formatted correctly."""

        assert _format_field_location(("body", "address", "city")) == "address.city"
        assert _format_field_location(("body", "items", 0, "name")) == "items.0.name"

    def test_format_single_error_missing(self) -> None:
        """Test that missing field error is formatted correctly."""

        error = {"loc": ("body", "email"), "type": "missing", "msg": "Field required"}
        assert _format_single_error(error) == "Field 'email' is required"

    def test_format_single_error_wrong_type(self) -> None:
        """Test that wrong type error is formatted correctly."""

        error = {"loc": ("body", "age"), "type": "int_parsing", "msg": "Input should be a valid integer"}
        assert _format_single_error(error) == "Field 'age' must be a valid integer"

    def test_format_single_error_string_type(self) -> None:
        """Test that string type error is formatted correctly."""

        error = {"loc": ("body", "name"), "type": "string_type", "msg": "Input should be a valid string"}
        assert _format_single_error(error) == "Field 'name' must be a string"

    def test_format_single_error_value_error(self) -> None:
        """Test that value error is formatted with original message."""

        error = {"loc": ("body", "email"), "type": "value_error", "msg": "Invalid email format"}
        assert _format_single_error(error) == "Field 'email': Invalid email format"
