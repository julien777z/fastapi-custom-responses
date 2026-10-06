from typing import Literal

import pytest
from pydantic import ValidationError

from fastapi_custom_responses import (
    ErrorResponseModel,
)
from tests.fixtures.models import AccessErrorCode
from tests.fixtures.responses import METADATA_BODY


class TestErrorResponseModel:
    """Tests for the documented error response schema."""

    def test_code_is_optional(self) -> None:
        """Test that ErrorResponseModel leaves the code unset when none is given."""

        assert ErrorResponseModel(success=False, error=METADATA_BODY.error).code is None

    def test_json_schema_exposes_code_as_optional(self) -> None:
        """Test that the generated JSON schema lists code as an optional property."""

        schema = ErrorResponseModel.model_json_schema()

        assert "code" in schema["properties"]
        assert "code" not in schema["required"]

    def test_enum_member(self) -> None:
        """Test that a parametrized model accepts a member of its code enum."""

        model = ErrorResponseModel[AccessErrorCode](
            success=False, error=METADATA_BODY.error, code=AccessErrorCode.PERMISSION_DENIED
        )

        assert model.code is AccessErrorCode.PERMISSION_DENIED

    def test_unknown_code(self) -> None:
        """Test that a parametrized model rejects a code outside its enum."""

        with pytest.raises(ValidationError):
            ErrorResponseModel[AccessErrorCode](success=False, error=METADATA_BODY.error, code="bogus")

    def test_enum_schema(self) -> None:
        """Test that parametrizing the model enumerates the code enum in its schema."""

        schema = ErrorResponseModel[AccessErrorCode].model_json_schema()

        assert schema["$defs"]["AccessErrorCode"]["enum"] == [code.value for code in AccessErrorCode]

    @pytest.mark.parametrize("code", list(AccessErrorCode), ids=lambda code: code.value)
    def test_selected_literal_validates_exact_values(self, code: AccessErrorCode) -> None:
        """Test that literal models enforce selected enum members."""

        model = ErrorResponseModel[Literal[AccessErrorCode.PERMISSION_DENIED]]

        if code == AccessErrorCode.PERMISSION_DENIED:
            assert model(success=False, error=METADATA_BODY.error, code=code).code == code
        else:
            with pytest.raises(ValidationError):
                model(success=False, error=METADATA_BODY.error, code=code)

        assert model(success=False, error=METADATA_BODY.error).code is None
        assert model(success=False, error=METADATA_BODY.error, code=None).code is None
