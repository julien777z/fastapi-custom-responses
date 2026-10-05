import pytest
from pydantic import ValidationError

from fastapi_custom_responses import (
    ErrorResponseModel,
)
from tests.conftest import (
    AccessErrorCode,
)


class TestErrorResponseModel:
    """Tests for the documented error response schema."""

    def test_code_is_optional(self) -> None:
        """Test that ErrorResponseModel leaves the code unset when none is given."""

        assert ErrorResponseModel(success=False, error="Denied").code is None

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
