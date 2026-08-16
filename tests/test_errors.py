from http import HTTPStatus
from inspect import Parameter, signature

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import ValidationError

from fastapi_custom_responses import (
    ErrorResponse,
    ErrorResponseModel,
    SuccessResponse,
    fastapi_responses,
)
from fastapi_custom_responses.errors import format_field_location, format_single_error
from tests.conftest import VALID_CONSTRAINED_PAYLOAD, AccessErrorCode, StandaloneErrorCode


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
        self, client: AsyncClient, payload_override: dict, expected_error: str
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

        response = await client.post(
            "/validate-constrained", json=VALID_CONSTRAINED_PAYLOAD.model_dump(mode="json")
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["success"] is True


class TestErrorEnvelope:
    """Tests for the envelope every failing path renders."""

    @pytest.mark.parametrize(
        ("path", "status_code", "expected_body"),
        [
            (
                "/error-response",
                HTTPStatus.BAD_REQUEST,
                {"success": False, "error": "Custom error message"},
            ),
            (
                "/error-response-not-found",
                HTTPStatus.NOT_FOUND,
                {"success": False, "error": "Item not found"},
            ),
            (
                "/error-response-from-status",
                HTTPStatus.FORBIDDEN,
                {
                    "success": False,
                    "error": "You don't have permission to perform this action",
                },
            ),
            (
                "/error-response-with-code",
                HTTPStatus.FORBIDDEN,
                {"success": False, "error": "Custom error message", "code": "permission_denied"},
            ),
            (
                "/error-response-from-status-with-code",
                HTTPStatus.FORBIDDEN,
                {
                    "success": False,
                    "error": "You don't have permission to perform this action",
                    "code": "permission_denied",
                },
            ),
            (
                "/http-exception",
                HTTPStatus.UNAUTHORIZED,
                {"success": False, "error": "Not authenticated"},
            ),
            (
                "/http-exception-unusual-status",
                HTTPStatus.IM_A_TEAPOT,
                {"success": False, "error": "I'm a teapot"},
            ),
            (
                "/value-error",
                HTTPStatus.BAD_REQUEST,
                {"success": False, "error": "Invalid value provided", "code": "invalid_value"},
            ),
            (
                "/general-exception",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "success": False,
                    "error": "An unexpected error occurred",
                    "code": "internal_error",
                },
            ),
        ],
        ids=[
            "custom_message",
            "custom_status",
            "from_status_code",
            "with_code",
            "from_status_code_with_code",
            "http_exception",
            "http_exception_unusual_status",
            "value_error",
            "general_exception",
        ],
    )
    async def test_renders_the_error_envelope(
        self, client: AsyncClient, path: str, status_code: HTTPStatus, expected_body: dict
    ) -> None:
        """Test that each failing path renders the envelope with its status and code."""

        response = await client.get(path)

        assert response.status_code == status_code
        assert response.json() == expected_body


class TestErrorResponseCode:
    """Tests for the error code carried by ErrorResponse."""

    def test_code_is_keyword_only(self) -> None:
        """Test that the error code can only be supplied by keyword."""

        assert signature(ErrorResponse).parameters["code"].kind is Parameter.KEYWORD_ONLY

    def test_accepts_a_code_declared_without_the_library_base(self) -> None:
        """Test that a code enum from a consumer that never imports the base is accepted."""

        error = ErrorResponse(
            "Not a member", HTTPStatus.FORBIDDEN, code=StandaloneErrorCode.MEMBERSHIP_REQUIRED
        )

        assert error.code == "membership_required"


class TestErrorResponseModel:
    """Tests for the documented error response schema."""

    @pytest.mark.parametrize(
        ("code_field", "expected_code"),
        [({"code": "permission_denied"}, "permission_denied"), ({}, None)],
        ids=["with_code", "without_code"],
    )
    def test_validates_code(self, code_field: dict, expected_code: str | None) -> None:
        """Test that ErrorResponseModel accepts a code and defaults it to None when absent."""

        model = ErrorResponseModel(success=False, error="Denied", **code_field)

        assert model.code == expected_code

    def test_error_defaults_to_the_generic_message(self) -> None:
        """Test that omitting the error message falls back to the generic one."""

        model = ErrorResponseModel(success=False)

        assert model.error == "An unexpected error occurred"

    def test_json_schema_exposes_code_as_optional(self) -> None:
        """Test that the generated JSON schema lists code as an optional property."""

        schema = ErrorResponseModel.model_json_schema()

        assert "code" in schema["properties"]
        assert "code" not in schema["required"]

    def test_parametrized_accepts_a_member(self) -> None:
        """Test that a parametrized model accepts a member of its code enum."""

        model = ErrorResponseModel[AccessErrorCode](
            success=False, error="Denied", code=AccessErrorCode.PERMISSION_DENIED
        )

        assert model.code is AccessErrorCode.PERMISSION_DENIED

    def test_parametrized_rejects_an_unknown_code(self) -> None:
        """Test that a parametrized model rejects a code outside its enum."""

        with pytest.raises(ValidationError):
            ErrorResponseModel[AccessErrorCode](success=False, error="Denied", code="bogus")

    def test_parametrized_schema_enumerates_its_codes(self) -> None:
        """Test that parametrizing the model enumerates the code enum in its schema."""

        schema = ErrorResponseModel[AccessErrorCode].model_json_schema()

        assert schema["$defs"]["AccessErrorCode"]["enum"] == ["permission_denied", "account_suspended"]


class TestFastapiResponses:
    """Tests for the FastAPI responses mapping helper."""

    def test_error_enum_parametrizes_the_envelope(self) -> None:
        """Test that an error code enum parametrizes the error envelope."""

        responses = fastapi_responses({HTTPStatus.FORBIDDEN: AccessErrorCode})

        assert responses[HTTPStatus.FORBIDDEN] == {
            "model": ErrorResponseModel[AccessErrorCode],
            "description": "You don't have permission to perform this action",
        }

    def test_none_documents_the_bare_envelope(self) -> None:
        """Test that None documents the error envelope without specific codes."""

        responses = fastapi_responses({HTTPStatus.NOT_FOUND: None})

        assert responses[HTTPStatus.NOT_FOUND] == {
            "model": ErrorResponseModel,
            "description": "Resource not found",
        }

    def test_code_enum_without_the_library_base_is_parametrized(self) -> None:
        """Test that a code enum owned by a consumer that never imports the base still documents."""

        responses = fastapi_responses({HTTPStatus.FORBIDDEN: StandaloneErrorCode})

        assert responses[HTTPStatus.FORBIDDEN]["model"] is ErrorResponseModel[StandaloneErrorCode]

    def test_success_model_is_passed_through(self) -> None:
        """Test that a success envelope is documented as given, leaving its description to FastAPI."""

        responses = fastapi_responses({HTTPStatus.ACCEPTED: SuccessResponse})

        assert responses[HTTPStatus.ACCEPTED] == {"model": SuccessResponse}

    def test_status_without_a_message_falls_back_to_its_phrase(self) -> None:
        """Test that a status the library has no message for is described by its status phrase."""

        responses = fastapi_responses({HTTPStatus.IM_A_TEAPOT: None})

        assert responses[HTTPStatus.IM_A_TEAPOT] == {
            "model": ErrorResponseModel,
            "description": HTTPStatus.IM_A_TEAPOT.phrase,
        }


class TestOpenApiSchema:
    """Tests for the OpenAPI document the library's models produce."""

    def test_documents_codes_and_envelopes_per_endpoint(self, documented_app: FastAPI) -> None:
        """Test that each code enum and envelope becomes its own named component."""

        spec = documented_app.openapi()
        schemas = spec["components"]["schemas"]
        responses = spec["paths"]["/reports"]["post"]["responses"]

        assert schemas["AccessErrorCode"]["enum"] == ["permission_denied", "account_suspended"]
        assert "Response_ValidationPayload_" in schemas

        forbidden = responses[str(int(HTTPStatus.FORBIDDEN))]
        envelope = forbidden["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]

        assert schemas[envelope]["properties"]["code"]["anyOf"] == [
            {"$ref": "#/components/schemas/AccessErrorCode"},
            {"type": "null"},
        ]


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
    def test_joins_the_field_parts(self, loc: tuple, expected: str) -> None:
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
    def test_formats_the_message(self, error: dict, expected: str) -> None:
        """Test that validation error dicts are formatted into human-readable messages."""

        assert format_single_error(error) == expected
