from http import HTTPStatus

import pytest
from fastapi.exceptions import RequestValidationError
from pydantic_core import ErrorDetails

from fastapi_custom_responses.errors import (
    format_field_location,
    format_single_error,
    format_validation_errors,
)


class TestValidationFormatting:
    """Tests for validation message formatting."""

    @pytest.mark.parametrize(
        ("loc", "expected"),
        [
            (("body", "email"), "email"),
            (("query", "page"), "page"),
            (("path", "id"), "id"),
            (("body", "address", "city"), "address.city"),
            (("body", "body", "name"), "body.name"),
            (("body", "items", 0, "name"), "items.0.name"),
            (("body",), "body"),
            ((), "field"),
        ],
        ids=[
            "body",
            "query",
            "path",
            "nested_object",
            "transport_named_field",
            "nested_array",
            "only_prefix",
            "empty",
        ],
    )
    def test_field_location(self, loc: tuple[int | str, ...], expected: str) -> None:
        """Test that field location tuples are formatted into human-readable names."""

        assert format_field_location(loc) == expected

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (
                ErrorDetails(loc=("body", "x"), type="unrecognized", msg="Something", input=None),
                "Field 'x': Something",
            ),
            (
                ErrorDetails(loc=("body", "x"), type="unrecognized", msg="", input=None),
                "Field 'x' is invalid",
            ),
            (
                ErrorDetails(loc=("body", "email"), type="missing", msg="Field required", input=None),
                "Field 'email' is required",
            ),
            (
                ErrorDetails(
                    loc=("body", "age"), type="int_parsing", msg="Input should be a valid integer", input=None
                ),
                "Field 'age' must be a valid integer",
            ),
            (
                ErrorDetails(
                    loc=("body", "name"), type="string_type", msg="Input should be a valid string", input=None
                ),
                "Field 'name' must be a string",
            ),
            (
                ErrorDetails(
                    loc=("body", "email"),
                    type="value_error",
                    msg="Value error, Invalid email format",
                    input=None,
                ),
                "Invalid email format",
            ),
            (
                ErrorDetails(
                    loc=("body", "email"), type="value_error", msg="Invalid email format", input=None
                ),
                "Invalid email format",
            ),
            (
                ErrorDetails(
                    loc=("body", "name"),
                    type="string_too_short",
                    msg="String should have at least 3 characters",
                    ctx={"min_length": 3},
                    input=None,
                ),
                "Field 'name' must be at least 3 characters",
            ),
            (
                ErrorDetails(
                    loc=("body", "name"),
                    type="string_too_short",
                    msg="String should have at least 3 characters",
                    input=None,
                ),
                "Field 'name' is too short",
            ),
            (
                ErrorDetails(
                    loc=("body", "bio"),
                    type="string_too_long",
                    msg="String should have at most 100 characters",
                    ctx={"max_length": 100},
                    input=None,
                ),
                "Field 'bio' must be at most 100 characters",
            ),
            (
                ErrorDetails(
                    loc=("body", "bio"),
                    type="string_too_long",
                    msg="String should have at most 100 characters",
                    input=None,
                ),
                "Field 'bio' is too long",
            ),
            (
                ErrorDetails(
                    loc=("body", "tags"),
                    type="too_short",
                    msg="List should have at least 1 item after validation",
                    ctx={"min_length": 1},
                    input=None,
                ),
                "Field 'tags' must have at least 1 item",
            ),
            (
                ErrorDetails(
                    loc=("body", "tags"),
                    type="too_short",
                    msg="List should have at least 3 items after validation",
                    ctx={"min_length": 3},
                    input=None,
                ),
                "Field 'tags' must have at least 3 items",
            ),
            (
                ErrorDetails(
                    loc=("body", "tags"),
                    type="too_long",
                    msg="List should have at most 5 items after validation",
                    ctx={"max_length": 5},
                    input=None,
                ),
                "Field 'tags' must have at most 5 items",
            ),
            (
                ErrorDetails(
                    loc=("body", "tags"),
                    type="too_long",
                    msg="List should have at most 1 item after validation",
                    ctx={"max_length": 1},
                    input=None,
                ),
                "Field 'tags' must have at most 1 item",
            ),
            (
                ErrorDetails(
                    loc=("body", "rating"),
                    type="greater_than",
                    msg="Input should be greater than 0",
                    ctx={"gt": 0},
                    input=None,
                ),
                "Field 'rating' must be greater than 0",
            ),
            (
                ErrorDetails(
                    loc=("body", "score"),
                    type="greater_than_equal",
                    msg="Input should be greater than or equal to 0",
                    ctx={"ge": 0},
                    input=None,
                ),
                "Field 'score' must be at least 0",
            ),
            (
                ErrorDetails(
                    loc=("body", "rating"),
                    type="less_than",
                    msg="Input should be less than 5",
                    ctx={"lt": 5},
                    input=None,
                ),
                "Field 'rating' must be less than 5",
            ),
            (
                ErrorDetails(
                    loc=("body", "score"),
                    type="less_than_equal",
                    msg="Input should be less than or equal to 100",
                    ctx={"le": 100},
                    input=None,
                ),
                "Field 'score' must be at most 100",
            ),
            (
                ErrorDetails(
                    loc=("body", "color"),
                    type="enum",
                    msg="Input should be 'red', 'green' or 'blue'",
                    ctx={"expected": "'red', 'green' or 'blue'"},
                    input=None,
                ),
                "Field 'color' must be one of: 'red', 'green' or 'blue'",
            ),
            (
                ErrorDetails(
                    loc=("body", "color"),
                    type="enum",
                    msg="Input should be 'red', 'green' or 'blue'",
                    input=None,
                ),
                "Field 'color' has an invalid value",
            ),
            (
                ErrorDetails(
                    loc=("body", "score"),
                    type="greater_than_equal",
                    msg="Input should be greater than or equal to 0",
                    input=None,
                ),
                "Field 'score' has an invalid value",
            ),
        ],
        ids=[
            "unknown_type_with_message",
            "unknown_type_without_message",
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
    def test_error_message(self, error: ErrorDetails, expected: str) -> None:
        """Test that validation error dicts are formatted into human-readable messages."""

        assert format_single_error(error) == expected

    def test_empty_errors(self) -> None:
        """Test that an empty validation error list renders the generic bad request message."""

        assert format_validation_errors(RequestValidationError([])) == HTTPStatus.BAD_REQUEST.phrase
