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


class TestConstrainedValidationErrors:
    """Tests for constraint-aware validation error messages."""

    client: AsyncClient

    @pytest.mark.asyncio
    async def test_string_too_short_includes_min_length(self) -> None:
        """Test that string_too_short error includes the minimum length."""

        response = await self.client.post(
            "/validate-constrained",
            json={"username": "ab", "score": 50, "rating": 2.5, "color": "red", "tags": ["a"]},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Field 'username' must be at least 3 characters"

    @pytest.mark.asyncio
    async def test_string_too_long_includes_max_length(self) -> None:
        """Test that string_too_long error includes the maximum length."""

        response = await self.client.post(
            "/validate-constrained",
            json={"username": "a" * 21, "score": 50, "rating": 2.5, "color": "red", "tags": ["a"]},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Field 'username' must be at most 20 characters"

    @pytest.mark.asyncio
    async def test_greater_than_equal_includes_minimum(self) -> None:
        """Test that greater_than_equal error includes the minimum value."""

        response = await self.client.post(
            "/validate-constrained",
            json={"username": "alice", "score": -1, "rating": 2.5, "color": "red", "tags": ["a"]},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Field 'score' must be at least 0"

    @pytest.mark.asyncio
    async def test_less_than_equal_includes_maximum(self) -> None:
        """Test that less_than_equal error includes the maximum value."""

        response = await self.client.post(
            "/validate-constrained",
            json={"username": "alice", "score": 101, "rating": 2.5, "color": "red", "tags": ["a"]},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Field 'score' must be at most 100"

    @pytest.mark.asyncio
    async def test_greater_than_includes_bound(self) -> None:
        """Test that greater_than error includes the bound value."""

        response = await self.client.post(
            "/validate-constrained",
            json={"username": "alice", "score": 50, "rating": 0, "color": "red", "tags": ["a"]},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Field 'rating' must be greater than 0"

    @pytest.mark.asyncio
    async def test_less_than_includes_bound(self) -> None:
        """Test that less_than error includes the bound value."""

        response = await self.client.post(
            "/validate-constrained",
            json={"username": "alice", "score": 50, "rating": 5, "color": "red", "tags": ["a"]},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Field 'rating' must be less than 5"

    @pytest.mark.asyncio
    async def test_enum_includes_expected_values(self) -> None:
        """Test that enum error includes the allowed values."""

        response = await self.client.post(
            "/validate-constrained",
            json={"username": "alice", "score": 50, "rating": 2.5, "color": "purple", "tags": ["a"]},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "color" in data["error"]
        assert "must be one of" in data["error"]

    @pytest.mark.asyncio
    async def test_list_too_short_includes_min_length(self) -> None:
        """Test that too_short error for lists includes the minimum count."""

        response = await self.client.post(
            "/validate-constrained",
            json={"username": "alice", "score": 50, "rating": 2.5, "color": "red", "tags": []},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Field 'tags' must have at least 1 item"

    @pytest.mark.asyncio
    async def test_list_too_long_includes_max_length(self) -> None:
        """Test that too_long error for lists includes the maximum count."""

        response = await self.client.post(
            "/validate-constrained",
            json={
                "username": "alice",
                "score": 50,
                "rating": 2.5,
                "color": "red",
                "tags": ["a", "b", "c", "d", "e", "f"],
            },
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Field 'tags' must have at most 5 items"

    @pytest.mark.asyncio
    async def test_value_error_strips_pydantic_prefix(self) -> None:
        """Test that value_error strips the 'Value error, ' prefix Pydantic adds."""

        response = await self.client.post("/validate-value-error", json={"code": "abc"})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Field 'code': Code must be exactly 4 digits"

    @pytest.mark.asyncio
    async def test_valid_constrained_request_succeeds(self) -> None:
        """Test that a valid request with all constraints met succeeds."""

        response = await self.client.post(
            "/validate-constrained",
            json={"username": "alice", "score": 50, "rating": 2.5, "color": "red", "tags": ["a"]},
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
        """Test that value error strips 'Value error, ' prefix."""

        error = {
            "loc": ("body", "email"),
            "type": "value_error",
            "msg": "Value error, Invalid email format",
        }

        assert _format_single_error(error) == "Field 'email': Invalid email format"

    def test_format_single_error_value_error_without_prefix(self) -> None:
        """Test that value error without prefix is passed through unchanged."""

        error = {"loc": ("body", "email"), "type": "value_error", "msg": "Invalid email format"}
        assert _format_single_error(error) == "Field 'email': Invalid email format"

    def test_format_single_error_string_too_short_with_ctx(self) -> None:
        """Test that string_too_short includes min_length from ctx."""

        error = {
            "loc": ("body", "name"),
            "type": "string_too_short",
            "msg": "String should have at least 3 characters",
            "ctx": {"min_length": 3},
        }

        assert _format_single_error(error) == "Field 'name' must be at least 3 characters"

    def test_format_single_error_string_too_short_without_ctx(self) -> None:
        """Test that string_too_short falls back when ctx is missing."""

        error = {
            "loc": ("body", "name"),
            "type": "string_too_short",
            "msg": "String should have at least 3 characters",
        }

        assert _format_single_error(error) == "Field 'name' is too short"

    def test_format_single_error_string_too_long_with_ctx(self) -> None:
        """Test that string_too_long includes max_length from ctx."""

        error = {
            "loc": ("body", "bio"),
            "type": "string_too_long",
            "msg": "String should have at most 100 characters",
            "ctx": {"max_length": 100},
        }

        assert _format_single_error(error) == "Field 'bio' must be at most 100 characters"

    def test_format_single_error_string_too_long_without_ctx(self) -> None:
        """Test that string_too_long falls back when ctx is missing."""

        error = {
            "loc": ("body", "bio"),
            "type": "string_too_long",
            "msg": "String should have at most 100 characters",
        }

        assert _format_single_error(error) == "Field 'bio' is too long"

    def test_format_single_error_too_short_with_ctx(self) -> None:
        """Test that too_short for lists includes min_length from ctx."""

        error = {
            "loc": ("body", "tags"),
            "type": "too_short",
            "msg": "List should have at least 1 item after validation",
            "ctx": {"min_length": 1},
        }

        assert _format_single_error(error) == "Field 'tags' must have at least 1 item"

    def test_format_single_error_too_short_plural(self) -> None:
        """Test that too_short uses 'items' for min_length > 1."""

        error = {
            "loc": ("body", "tags"),
            "type": "too_short",
            "msg": "List should have at least 3 items after validation",
            "ctx": {"min_length": 3},
        }

        assert _format_single_error(error) == "Field 'tags' must have at least 3 items"

    def test_format_single_error_too_long_with_ctx(self) -> None:
        """Test that too_long for lists includes max_length from ctx."""

        error = {
            "loc": ("body", "tags"),
            "type": "too_long",
            "msg": "List should have at most 5 items after validation",
            "ctx": {"max_length": 5},
        }

        assert _format_single_error(error) == "Field 'tags' must have at most 5 items"

    def test_format_single_error_too_long_singular(self) -> None:
        """Test that too_long uses 'item' for max_length == 1."""

        error = {
            "loc": ("body", "tags"),
            "type": "too_long",
            "msg": "List should have at most 1 item after validation",
            "ctx": {"max_length": 1},
        }

        assert _format_single_error(error) == "Field 'tags' must have at most 1 item"

    def test_format_single_error_greater_than_with_ctx(self) -> None:
        """Test that greater_than includes bound from ctx."""

        error = {
            "loc": ("body", "rating"),
            "type": "greater_than",
            "msg": "Input should be greater than 0",
            "ctx": {"gt": 0},
        }

        assert _format_single_error(error) == "Field 'rating' must be greater than 0"

    def test_format_single_error_greater_than_equal_with_ctx(self) -> None:
        """Test that greater_than_equal includes bound from ctx."""

        error = {
            "loc": ("body", "score"),
            "type": "greater_than_equal",
            "msg": "Input should be greater than or equal to 0",
            "ctx": {"ge": 0},
        }

        assert _format_single_error(error) == "Field 'score' must be at least 0"

    def test_format_single_error_less_than_with_ctx(self) -> None:
        """Test that less_than includes bound from ctx."""

        error = {
            "loc": ("body", "rating"),
            "type": "less_than",
            "msg": "Input should be less than 5",
            "ctx": {"lt": 5},
        }

        assert _format_single_error(error) == "Field 'rating' must be less than 5"

    def test_format_single_error_less_than_equal_with_ctx(self) -> None:
        """Test that less_than_equal includes bound from ctx."""

        error = {
            "loc": ("body", "score"),
            "type": "less_than_equal",
            "msg": "Input should be less than or equal to 100",
            "ctx": {"le": 100},
        }

        assert _format_single_error(error) == "Field 'score' must be at most 100"

    def test_format_single_error_enum_with_ctx(self) -> None:
        """Test that enum error includes expected values from ctx."""

        error = {
            "loc": ("body", "color"),
            "type": "enum",
            "msg": "Input should be 'red', 'green' or 'blue'",
            "ctx": {"expected": "'red', 'green' or 'blue'"},
        }

        assert _format_single_error(error) == "Field 'color' must be one of: 'red', 'green' or 'blue'"

    def test_format_single_error_enum_without_ctx(self) -> None:
        """Test that enum error falls back when ctx is missing."""

        error = {
            "loc": ("body", "color"),
            "type": "enum",
            "msg": "Input should be 'red', 'green' or 'blue'",
        }

        assert _format_single_error(error) == "Field 'color' has an invalid value"

    def test_format_single_error_comparison_without_ctx(self) -> None:
        """Test that comparison errors fall back when ctx is missing."""

        error = {
            "loc": ("body", "score"),
            "type": "greater_than_equal",
            "msg": "Input should be greater than or equal to 0",
        }

        assert _format_single_error(error) == "Field 'score' has an invalid value"
