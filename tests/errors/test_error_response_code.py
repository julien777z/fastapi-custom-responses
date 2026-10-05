from http import HTTPStatus
from inspect import Parameter, signature

from fastapi_custom_responses import (
    ErrorResponse,
)


class TestErrorResponseCode:
    """Tests for the error code carried by ErrorResponse."""

    def test_code_is_keyword_only(self) -> None:
        """Test that the error code can only be supplied by keyword."""

        assert signature(ErrorResponse).parameters["code"].kind is Parameter.KEYWORD_ONLY

    def test_an_unnamed_error_carries_no_code(self) -> None:
        """Test that an error raised without a code carries none rather than restating its status."""

        assert ErrorResponse("boom", HTTPStatus.FORBIDDEN).code is None
