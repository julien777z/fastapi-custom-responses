from http import HTTPStatus

from fastapi import FastAPI


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

        bad_request = responses[str(int(HTTPStatus.BAD_REQUEST))]
        union_envelope = bad_request["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]

        assert schemas[union_envelope]["properties"]["code"]["anyOf"] == [
            {"$ref": "#/components/schemas/AccessErrorCode"},
            {"$ref": "#/components/schemas/DefaultErrorCode"},
            {"type": "null"},
        ]
        assert schemas["DefaultErrorCode"]["enum"] == ["validation_error", "invalid_value", "internal_error"]
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
            {"enum": ["permission_denied", "invalid_value"], "type": "string"},
            {"type": "null"},
        ]
        assert schemas[conflict_name]["properties"]["code"]["anyOf"] == [
            {"const": "account_suspended", "type": "string"},
            {"type": "null"},
        ]
