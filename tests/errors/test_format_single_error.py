from typing import Any

import pytest

from fastapi_custom_responses.errors import (
    format_single_error,
)


class TestFormatSingleError:
    """Tests for format_single_error helper."""

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (
                {"loc": ("body", "x"), "type": "unrecognized", "msg": "Something"},
                "Field 'x': Something",
            ),
            (
                {"loc": ("body", "x"), "type": "unrecognized"},
                "Field 'x' is invalid",
            ),
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
    def test_formats_the_message(self, error: dict[str, Any], expected: str) -> None:
        """Test that validation error dicts are formatted into human-readable messages."""

        assert format_single_error(error) == expected
