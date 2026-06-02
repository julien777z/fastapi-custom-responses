from http import HTTPStatus

from httpx import AsyncClient
import pytest

from fastapi_custom_responses.errors import format_field_location, format_single_error

VALID_CONSTRAINED_PAYLOAD: dict = {
    "username": "alice",
    "score": 50,
    "rating": 2.5,
    "color": "red",
    "tags": ["a"],
}


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
        self, payload_override: dict, expected_error: str
    ) -> None:
        """Test that constrained field violations produce specific error messages."""

        payload = {**VALID_CONSTRAINED_PAYLOAD, **payload_override}
        response = await self.client.post("/validate-constrained", json=payload)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == expected_error

    @pytest.mark.asyncio
    async def test_enum_includes_expected_values(self) -> None:
        """Test that enum error includes the allowed values."""

        payload = {**VALID_CONSTRAINED_PAYLOAD, "color": "purple"}
        response = await self.client.post("/validate-constrained", json=payload)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "color" in data["error"]
        assert "must be one of" in data["error"]

    @pytest.mark.asyncio
    async def test_value_error_strips_pydantic_prefix(self) -> None:
        """Test that value_error strips the 'Value error, ' prefix Pydantic adds."""

        response = await self.client.post("/validate-value-error", json={"code": "abc"})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Code must be exactly 4 digits"

    @pytest.mark.asyncio
    async def test_valid_constrained_request_succeeds(self) -> None:
        """Test that a valid request with all constraints met succeeds."""

        response = await self.client.post("/validate-constrained", json=VALID_CONSTRAINED_PAYLOAD)

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
        """Test that unhandled exceptions return generic 500 message."""

        try:
            response = await self.client.get("/general-exception")
            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            data = response.json()
            assert data["success"] is False
            assert data["error"] == "An unexpected error occurred"
        except RuntimeError as e:
            # In test mode, FastAPI may re-raise the exception
            assert str(e) == "Something went wrong"


class TestFormatFieldLocation:
    """Tests for format_field_location helper."""

    @pytest.mark.parametrize(
        ("loc", "expected"),
        [
            (("body", "email"), "email"),
            (("query", "page"), "page"),
            (("path", "id"), "id"),
            (("body", "address", "city"), "address.city"),
            (("body", "items", 0, "name"), "items.0.name"),
        ],
        ids=["body", "query", "path", "nested_object", "nested_array"],
    )
    def test_format_field_location(self, loc: tuple, expected: str) -> None:
        """Test that field location tuples are formatted into human-readable names."""

        assert format_field_location(loc) == expected


class TestFormatSingleError:
    """Tests for format_single_error helper."""

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (
                {"loc": ("body", "email"), "type": "missing", "msg": "Field required"},
                "Field 'email' is required",
            ),
            (
                {"loc": ("body", "age"), "type": "int_parsing", "msg": "Input should be a valid integer"},
                "Field 'age' must be a valid integer",
            ),
            (
                {"loc": ("body", "name"), "type": "string_type", "msg": "Input should be a valid string"},
                "Field 'name' must be a string",
            ),
            (
                {"loc": ("body", "email"), "type": "value_error", "msg": "Value error, Invalid email format"},
                "Invalid email format",
            ),
            (
                {"loc": ("body", "email"), "type": "value_error", "msg": "Invalid email format"},
                "Invalid email format",
            ),
            (
                {
                    "loc": ("body", "name"),
                    "type": "string_too_short",
                    "msg": "String should have at least 3 characters",
                    "ctx": {"min_length": 3},
                },
                "Field 'name' must be at least 3 characters",
            ),
            (
                {
                    "loc": ("body", "name"),
                    "type": "string_too_short",
                    "msg": "String should have at least 3 characters",
                },
                "Field 'name' is too short",
            ),
            (
                {
                    "loc": ("body", "bio"),
                    "type": "string_too_long",
                    "msg": "String should have at most 100 characters",
                    "ctx": {"max_length": 100},
                },
                "Field 'bio' must be at most 100 characters",
            ),
            (
                {
                    "loc": ("body", "bio"),
                    "type": "string_too_long",
                    "msg": "String should have at most 100 characters",
                },
                "Field 'bio' is too long",
            ),
            (
                {
                    "loc": ("body", "tags"),
                    "type": "too_short",
                    "msg": "List should have at least 1 item after validation",
                    "ctx": {"min_length": 1},
                },
                "Field 'tags' must have at least 1 item",
            ),
            (
                {
                    "loc": ("body", "tags"),
                    "type": "too_short",
                    "msg": "List should have at least 3 items after validation",
                    "ctx": {"min_length": 3},
                },
                "Field 'tags' must have at least 3 items",
            ),
            (
                {
                    "loc": ("body", "tags"),
                    "type": "too_long",
                    "msg": "List should have at most 5 items after validation",
                    "ctx": {"max_length": 5},
                },
                "Field 'tags' must have at most 5 items",
            ),
            (
                {
                    "loc": ("body", "tags"),
                    "type": "too_long",
                    "msg": "List should have at most 1 item after validation",
                    "ctx": {"max_length": 1},
                },
                "Field 'tags' must have at most 1 item",
            ),
            (
                {
                    "loc": ("body", "rating"),
                    "type": "greater_than",
                    "msg": "Input should be greater than 0",
                    "ctx": {"gt": 0},
                },
                "Field 'rating' must be greater than 0",
            ),
            (
                {
                    "loc": ("body", "score"),
                    "type": "greater_than_equal",
                    "msg": "Input should be greater than or equal to 0",
                    "ctx": {"ge": 0},
                },
                "Field 'score' must be at least 0",
            ),
            (
                {
                    "loc": ("body", "rating"),
                    "type": "less_than",
                    "msg": "Input should be less than 5",
                    "ctx": {"lt": 5},
                },
                "Field 'rating' must be less than 5",
            ),
            (
                {
                    "loc": ("body", "score"),
                    "type": "less_than_equal",
                    "msg": "Input should be less than or equal to 100",
                    "ctx": {"le": 100},
                },
                "Field 'score' must be at most 100",
            ),
            (
                {
                    "loc": ("body", "color"),
                    "type": "enum",
                    "msg": "Input should be 'red', 'green' or 'blue'",
                    "ctx": {"expected": "'red', 'green' or 'blue'"},
                },
                "Field 'color' must be one of: 'red', 'green' or 'blue'",
            ),
            (
                {
                    "loc": ("body", "color"),
                    "type": "enum",
                    "msg": "Input should be 'red', 'green' or 'blue'",
                },
                "Field 'color' has an invalid value",
            ),
            (
                {
                    "loc": ("body", "score"),
                    "type": "greater_than_equal",
                    "msg": "Input should be greater than or equal to 0",
                },
                "Field 'score' has an invalid value",
            ),
        ],
        ids=[
            "missing",
            "int_parsing",
            "string_type",
            "value_error_with_prefix",
            "value_error_without_prefix",
            "string_too_short_with_ctx",
            "string_too_short_without_ctx",
            "string_too_long_with_ctx",
            "string_too_long_without_ctx",
            "list_too_short_singular",
            "list_too_short_plural",
            "list_too_long_with_ctx",
            "list_too_long_singular",
            "greater_than",
            "greater_than_equal",
            "less_than",
            "less_than_equal",
            "enum_with_ctx",
            "enum_without_ctx",
            "comparison_without_ctx",
        ],
    )
    def test_format_single_error(self, error: dict, expected: str) -> None:
        """Test that validation error dicts are formatted into human-readable messages."""

        assert format_single_error(error) == expected
