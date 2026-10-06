from http import HTTPStatus

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_custom_responses import DefaultErrorCode, ErrorResponseModel
from tests.fixtures.models import AccessErrorCode
from tests.fixtures.responses import METADATA, METADATA_BODY


class TestResponseDocumentation:
    """Tests for native response documentation."""

    def test_validation_status_and_body_match_documentation(self, app: FastAPI) -> None:
        """Test that validation documentation matches the actual 400 envelope."""

        response = TestClient(app).post("/validate", json={})

        spec = app.openapi()
        responses = spec["paths"]["/validate"]["post"]["responses"]

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "422" not in responses
        assert "HTTPValidationError" not in spec["components"]["schemas"]

        schema_name = responses["400"]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
        schema = spec["components"]["schemas"][schema_name]

        assert response.json()["success"] is False
        assert response.json()["code"] in schema["properties"]["code"]["anyOf"][0]["enum"]

    def test_native_metadata_and_explicit_keys_are_preserved(self, response_metadata_app: FastAPI) -> None:
        """Test that metadata coexists with the selected error schema."""

        responses = response_metadata_app.openapi()["paths"]["/metadata"]["get"]["responses"]
        forbidden = responses["403"]
        content = forbidden["content"]

        assert forbidden["description"] == METADATA.description
        assert forbidden["headers"]["Retry-After"]["schema"] == {"type": "integer"}
        assert forbidden["links"]["resource"]["operationId"] == METADATA.operation_id
        assert "schema" in content["application/json"]
        assert content["application/json"]["examples"]["denied"]["value"]["code"] == METADATA_BODY.code
        assert content["text/plain"]["schema"] == {"type": "string"}
        assert responses["422"]["description"] == METADATA.explicit_refusal
        assert responses["499"]["description"] == METADATA.cancelled
        assert responses["4XX"]["description"] == METADATA.client_failures
        assert responses["default"]["description"] == METADATA.other_failures

    def test_additional_schemas_do_not_validate(self, response_metadata_app: FastAPI) -> None:
        """Test that additional response schemas do not validate raised errors."""

        client = TestClient(response_metadata_app)

        assert client.get("/metadata?count=1").json() == {"success": True}

        error = client.get("/metadata?count=0")

        assert error.status_code == HTTPStatus.FORBIDDEN
        assert error.json()["code"] == AccessErrorCode.ACCOUNT_SUSPENDED

    def test_documents_codes_and_envelopes_per_endpoint(self, documented_app: FastAPI) -> None:
        """Test that each code enum and envelope becomes its own named component."""

        spec = documented_app.openapi()
        schemas = spec["components"]["schemas"]
        responses = spec["paths"]["/reports"]["post"]["responses"]

        assert schemas["AccessErrorCode"]["enum"] == [code.value for code in AccessErrorCode]
        assert "Response_ValidationPayload_" in schemas

        forbidden = responses[str(int(HTTPStatus.FORBIDDEN))]
        envelope = forbidden["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]

        assert schemas[envelope]["properties"]["code"]["anyOf"] == [
            {"$ref": "#/components/schemas/AccessErrorCode"},
            {"type": "null"},
        ]

        bad_request = responses[str(int(HTTPStatus.BAD_REQUEST))]
        union_envelope = bad_request["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]

        assert schemas[union_envelope]["properties"]["code"]["anyOf"] == [
            {"$ref": "#/components/schemas/AccessErrorCode"},
            {"$ref": "#/components/schemas/DefaultErrorCode"},
            {"type": "null"},
        ]
        assert schemas["DefaultErrorCode"]["enum"] == [code.value for code in DefaultErrorCode]
        assert forbidden["description"] == HTTPStatus.FORBIDDEN.phrase

    def test_selected_codes_reach_each_status_schema(self, documented_app: FastAPI) -> None:
        """Test that distinct selected subsets retain their nullable field schemas in OpenAPI."""

        spec = documented_app.openapi()
        schemas = spec["components"]["schemas"]
        responses = spec["paths"]["/selected"]["post"]["responses"]
        forbidden = responses[str(int(HTTPStatus.FORBIDDEN))]
        conflict = responses[str(int(HTTPStatus.CONFLICT))]
        forbidden_name = forbidden["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
        conflict_name = conflict["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]

        assert schemas[forbidden_name]["properties"]["code"]["anyOf"] == [
            {
                "enum": [AccessErrorCode.PERMISSION_DENIED.value, DefaultErrorCode.INVALID_VALUE.value],
                "type": "string",
            },
            {"type": "null"},
        ]
        assert schemas[conflict_name]["properties"]["code"]["anyOf"] == [
            {"const": AccessErrorCode.ACCOUNT_SUSPENDED.value, "type": "string"},
            {"type": "null"},
        ]
