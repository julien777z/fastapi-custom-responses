from http import HTTPStatus
from inspect import Parameter, signature
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from fastapi_custom_responses import PaginatedResponse
from tests.conftest import SAMPLE_PAYLOAD, ValidationPayload


class TestSuccessEnvelopes:
    """Tests for the shape of the success response envelopes."""

    @pytest.mark.parametrize(
        ("path", "expected_body"),
        [
            ("/response-with-data", {"success": True, "data": SAMPLE_PAYLOAD.model_dump()}),
            ("/success-response", {"success": True}),
            (
                "/paginated-response",
                {
                    "success": True,
                    "data": [SAMPLE_PAYLOAD.model_dump()],
                    "meta": {"offset": 0, "limit": 10, "total": 1},
                },
            ),
        ],
        ids=["with_data", "payload_free", "paginated"],
    )
    async def test_renders_the_success_envelope(
        self, client: AsyncClient, path: str, expected_body: dict[str, Any]
    ) -> None:
        """Test that each success envelope emits its documented body and nothing more."""

        response = await client.get(path)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == expected_body


class TestBuildPage:
    """Tests for building a paginated response from a page of items."""

    def test_assembles_the_envelope_and_metadata(self) -> None:
        """Test that a page of items and its bounds become a complete paginated response."""

        page = PaginatedResponse.build_page([SAMPLE_PAYLOAD], offset=20, limit=10, total=57)

        assert page.model_dump() == {
            "success": True,
            "data": [SAMPLE_PAYLOAD.model_dump()],
            "meta": {"offset": 20, "limit": 10, "total": 57},
        }

    def test_accepts_an_empty_page(self) -> None:
        """Test that a page past the end of the results carries no items and the real total."""

        page = PaginatedResponse.build_page([], offset=90, limit=10, total=57)

        assert page.model_dump() == {
            "success": True,
            "data": [],
            "meta": {"offset": 90, "limit": 10, "total": 57},
        }

    def test_bounds_are_keyword_only(self) -> None:
        """Test that the page bounds can only be supplied by keyword and cannot be transposed."""

        bounds = signature(PaginatedResponse.build_page).parameters

        assert all(bounds[name].kind is Parameter.KEYWORD_ONLY for name in ("offset", "limit", "total"))

    def test_parametrized_page_accepts_its_item_type(self) -> None:
        """Test that a parametrized paginated response carries items of the type it names."""

        page = PaginatedResponse[ValidationPayload].build_page([SAMPLE_PAYLOAD], offset=0, limit=10, total=1)

        assert page.data == [SAMPLE_PAYLOAD]

    def test_parametrized_page_rejects_a_foreign_item(self) -> None:
        """Test that a parametrized paginated response rejects an item of the wrong shape."""

        with pytest.raises(ValidationError):
            PaginatedResponse[ValidationPayload].build_page([{"unrelated": 1}], offset=0, limit=10, total=1)
