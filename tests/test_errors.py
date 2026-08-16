from http import HTTPStatus
from inspect import Parameter, signature

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import ValidationError

from fastapi_custom_responses import (
    ErrorResponse,
    ErrorResponseModel,
    Response,
    SuccessResponse,
    fastapi_responses,
)
from fastapi_custom_responses.errors import (
    STATUS_ERROR_CODES,
    format_field_location,
    format_single_error,
)
from tests.conftest import AccessErrorCode, StandaloneErrorCode, ValidationPayload

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

    async def test_validation_error_missing_field(self) -> None:
        """Test that POST with missing required field returns 400 with human-readable message."""

        response = await self.client.post("/validate", json={"name": "John", "age": 30})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": "Field 'email' is required",
            "code": "validation_error",
        }

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

    async def test_validation_error_multiple_errors(self) -> None:
        """Test that POST with multiple errors returns combined message."""

        response = await self.client.post("/validate", json={"name": 123})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["success"] is False
        assert "age" in data["error"] or "email" in data["error"]

    async def test_validation_error_invalid_json(self) -> None:
        """Test that POST with invalid JSON returns 400."""

        response = await self.client.post(
            "/validate", content="not valid json", headers={"Content-Type": "application/json"}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["success"] is False

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
    async def test_constrained_field_error(self, payload_override: dict, expected_error: str) -> None:
        """Test that constrained field violations produce specific error messages."""

        payload = {**VALID_CONSTRAINED_PAYLOAD, **payload_override}
        response = await self.client.post("/validate-constrained", json=payload)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == expected_error

    async def test_enum_includes_expected_values(self) -> None:
        """Test that enum error includes the allowed values."""

        payload = {**VALID_CONSTRAINED_PAYLOAD, "color": "purple"}
        response = await self.client.post("/validate-constrained", json=payload)

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "color" in data["error"]
        assert "must be one of" in data["error"]

    async def test_value_error_strips_pydantic_prefix(self) -> None:
        """Test that value_error strips the 'Value error, ' prefix Pydantic adds."""

        response = await self.client.post("/validate-value-error", json={"code": "abc"})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert data["error"] == "Code must be exactly 4 digits"

    async def test_valid_constrained_request_succeeds(self) -> None:
        """Test that a valid request with all constraints met succeeds."""

        response = await self.client.post("/validate-constrained", json=VALID_CONSTRAINED_PAYLOAD)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["success"] is True


class TestErrorResponse:
    """Tests for ErrorResponse exception handling."""

    client: AsyncClient

    async def test_error_response_custom_message(self) -> None:
        """Test that raising ErrorResponse returns custom message."""

        response = await self.client.get("/error-response")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {"success": False, "error": "Custom error message", "code": "bad_request"}

    async def test_error_response_custom_status_code(self) -> None:
        """Test that ErrorResponse can use different status codes."""

        response = await self.client.get("/error-response-not-found")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json() == {"success": False, "error": "Item not found", "code": "not_found"}

    async def test_error_response_from_status_code(self) -> None:
        """Test that ErrorResponse.from_status_code() uses predefined messages."""

        response = await self.client.get("/error-response-from-status")

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json() == {
            "success": False,
            "error": "You don't have permission to perform this action",
            "code": "forbidden",
        }

    async def test_error_response_with_code(self) -> None:
        """Test that ErrorResponse with a code emits that code in the envelope."""

        response = await self.client.get("/error-response-with-code")

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json() == {
            "success": False,
            "error": "Custom error message",
            "code": "permission_denied",
        }

    async def test_error_response_from_status_code_with_code(self) -> None:
        """Test that from_status_code() forwards the code into the envelope."""

        response = await self.client.get("/error-response-from-status-with-code")

        assert response.status_code == HTTPStatus.FORBIDDEN
        assert response.json() == {
            "success": False,
            "error": "You don't have permission to perform this action",
            "code": "permission_denied",
        }


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


class TestStatusErrorCodes:
    """Tests for codes derived from HTTP statuses."""

    @pytest.mark.parametrize(
        ("status_code", "expected_code"),
        [
            (HTTPStatus.UNAUTHORIZED, "unauthorized"),
            (HTTPStatus.FORBIDDEN, "forbidden"),
            (HTTPStatus.NOT_FOUND, "not_found"),
            (HTTPStatus.BAD_REQUEST, "bad_request"),
            (HTTPStatus.INTERNAL_SERVER_ERROR, "internal_server_error"),
            (HTTPStatus.IM_A_TEAPOT, "im_a_teapot"),
        ],
        ids=["unauthorized", "forbidden", "not_found", "bad_request", "internal", "unusual"],
    )
    def test_derives_code_from_status(self, status_code: HTTPStatus, expected_code: str) -> None:
        """Test that an error status derives its code from the status name."""

        assert STATUS_ERROR_CODES.get(status_code) == expected_code

    def test_non_standard_status_has_no_code(self) -> None:
        """Test that a status outside HTTPStatus derives no code."""

        assert STATUS_ERROR_CODES.get(499) is None

    def test_success_statuses_have_no_code(self) -> None:
        """Test that only error statuses carry codes."""

        assert all(status >= HTTPStatus.BAD_REQUEST for status in STATUS_ERROR_CODES)

    def test_covers_every_error_status(self) -> None:
        """Test that every error status the interpreter knows carries a code."""

        error_statuses = {status for status in HTTPStatus if status >= HTTPStatus.BAD_REQUEST}

        assert error_statuses <= set(STATUS_ERROR_CODES)


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

    def test_status_without_a_message_omits_the_description(self) -> None:
        """Test that a status the library has no message for carries no description."""

        responses = fastapi_responses({HTTPStatus.IM_A_TEAPOT: None})

        assert responses[HTTPStatus.IM_A_TEAPOT] == {"model": ErrorResponseModel}


class TestOpenApiSchema:
    """Tests for the OpenAPI document the library's models produce."""

    def test_documents_codes_and_envelopes_per_endpoint(self) -> None:
        """Test that each code enum and envelope becomes its own named component."""

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

        spec = app.openapi()
        schemas = spec["components"]["schemas"]
        responses = spec["paths"]["/reports"]["post"]["responses"]

        assert schemas["AccessErrorCode"]["enum"] == ["permission_denied", "account_suspended"]
        assert "ErrorResponseModel_AccessErrorCode_" in schemas
        assert "Response_ValidationPayload_" in schemas

        forbidden = responses[str(int(HTTPStatus.FORBIDDEN))]
        assert forbidden["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponseModel_AccessErrorCode_"
        }
        assert forbidden["description"] == "You don't have permission to perform this action"


class TestHTTPExceptionHandler:
    """Tests for HTTPException handling."""

    client: AsyncClient

    async def test_http_exception_handler(self) -> None:
        """Test that HTTPException is formatted correctly."""

        response = await self.client.get("/http-exception")

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json() == {"success": False, "error": "Not authenticated", "code": "unauthorized"}

    async def test_http_exception_unusual_status(self) -> None:
        """Test that an unusual status still derives its own code."""

        response = await self.client.get("/http-exception-unusual-status")

        assert response.status_code == HTTPStatus.IM_A_TEAPOT
        assert response.json() == {
            "success": False,
            "error": "I'm a teapot",
            "code": "im_a_teapot",
        }


class TestValueErrorHandler:
    """Tests for ValueError handling."""

    client: AsyncClient

    async def test_value_error_handler(self) -> None:
        """Test that ValueError returns str(exc)."""

        response = await self.client.get("/value-error")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {
            "success": False,
            "error": "Invalid value provided",
            "code": "invalid_value",
        }


class TestGeneralExceptionHandler:
    """Tests for unhandled exception handling."""

    client: AsyncClient

    async def test_general_exception_handler(self) -> None:
        """Test that an unhandled exception renders the generic server-error envelope."""

        response = await self.client.get("/general-exception")

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert response.json() == {
            "success": False,
            "error": "An unexpected error occurred",
            "code": "internal_server_error",
        }


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
