from http import HTTPStatus

import pytest
from pydantic import ValidationError

from fastapi_custom_responses import (
    DefaultErrorCode,
    ErrorResponseModel,
    SelectedErrorCodes,
    SuccessResponse,
    fastapi_responses,
)
from fastapi_custom_responses.errors import (
    documented_model,
)
from tests.conftest import (
    AccessErrorCode,
)


class TestFastapiResponses:
    """Tests for the FastAPI responses mapping helper."""

    def test_error_enum_parametrizes_the_envelope(self) -> None:
        """Test that an error code enum parametrizes the error envelope."""

        responses = fastapi_responses({HTTPStatus.FORBIDDEN: AccessErrorCode})

        assert responses[HTTPStatus.FORBIDDEN] == {"model": ErrorResponseModel[AccessErrorCode]}

    def test_none_documents_the_bare_envelope(self) -> None:
        """Test that None documents the error envelope without specific codes."""

        responses = fastapi_responses({HTTPStatus.NOT_FOUND: None})

        assert responses[HTTPStatus.NOT_FOUND] == {"model": ErrorResponseModel}

    def test_a_union_of_enums_parametrizes_the_envelope(self) -> None:
        """Test that a union of error code enums documents every code the status can carry."""

        responses = fastapi_responses({HTTPStatus.BAD_REQUEST: AccessErrorCode | DefaultErrorCode})

        assert responses[HTTPStatus.BAD_REQUEST] == {
            "model": ErrorResponseModel[AccessErrorCode | DefaultErrorCode]
        }

    def test_success_model_is_passed_through(self) -> None:
        """Test that a success envelope is documented as given."""

        responses = fastapi_responses({HTTPStatus.ACCEPTED: SuccessResponse})

        assert responses[HTTPStatus.ACCEPTED] == {"model": SuccessResponse}

    @pytest.mark.parametrize("code", [AccessErrorCode.PERMISSION_DENIED, DefaultErrorCode.INVALID_VALUE])
    def test_selected_members_validate_and_document_exactly(self, code: str) -> None:
        """Test that selected members across enums form the native response model's code contract."""

        selected = SelectedErrorCodes(
            codes=(AccessErrorCode.PERMISSION_DENIED, DefaultErrorCode.INVALID_VALUE)
        )
        model = documented_model(selected)

        accepted = model.model_validate({"success": False, "error": "Denied", "code": code})
        omitted = model.model_validate({"success": False, "error": "Denied"})
        nullable = model.model_validate({"success": False, "error": "Denied", "code": None})

        assert accepted.model_dump()["code"] == code
        assert omitted.model_dump()["code"] is None
        assert nullable.model_dump()["code"] is None
        assert issubclass(model, ErrorResponseModel)
        assert fastapi_responses({HTTPStatus.FORBIDDEN: selected})[HTTPStatus.FORBIDDEN] == {"model": model}

        schema = model.model_json_schema()

        assert schema["properties"]["code"]["anyOf"] == [
            {"enum": ["permission_denied", "invalid_value"], "type": "string"},
            {"type": "null"},
        ]
        assert schema["properties"]["code"]["default"] is None
        assert "code" not in schema["required"]

    @pytest.mark.parametrize("code", [AccessErrorCode.ACCOUNT_SUSPENDED, "unselected"])
    def test_selected_members_refuse_other_codes(self, code: str) -> None:
        """Test that an unselected enum member is refused by the documented error envelope."""

        selected = SelectedErrorCodes(codes=(AccessErrorCode.PERMISSION_DENIED,))
        model = documented_model(selected)

        with pytest.raises(ValidationError):
            model.model_validate({"success": False, "error": "Denied", "code": code})
