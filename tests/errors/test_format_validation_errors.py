from http import HTTPStatus

from fastapi.exceptions import RequestValidationError

from fastapi_custom_responses.errors import (
    format_validation_errors,
)


class TestFormatValidationErrors:
    """Tests for combining validation errors into one message."""

    def test_falls_back_when_there_are_no_errors(self) -> None:
        """Test that an empty validation error list renders the generic bad request message."""

        assert format_validation_errors(RequestValidationError([])) == HTTPStatus.BAD_REQUEST.phrase
