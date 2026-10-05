import pytest

from fastapi_custom_responses.errors import (
    format_field_location,
)


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
            (("body",), "body"),
            ((), "field"),
        ],
        ids=["body", "query", "path", "nested_object", "nested_array", "only_prefix", "empty"],
    )
    def test_joins_the_field_parts(self, loc: tuple, expected: str) -> None:
        """Test that field location tuples are formatted into human-readable names."""

        assert format_field_location(loc) == expected
