from http import HTTPStatus
from inspect import Parameter, signature

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from fastapi_custom_responses import PaginatedResponse
from tests.conftest import SAMPLE_PAYLOAD, ValidationPayload


class TestSuccessEnvelopes:
    """Tests for the shape of the success response envelopes."""

    async def test_response_carries_only_success_and_data(self, client: AsyncClient) -> None:
        """Test that a data-carrying response emits no fields beyond success and data."""

        response = await client.get("/response-with-data")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"success": True, "data": SAMPLE_PAYLOAD.model_dump()}

    async def test_success_response_carries_only_success(self, client: AsyncClient) -> None:
        """Test that a payload-free response emits nothing but success."""

        response = await client.get("/success-response")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"success": True}

    async def test_paginated_response_carries_data_and_meta(self, client: AsyncClient) -> None:
        """Test that a paginated response emits its data and pagination metadata."""

        response = await client.get("/paginated-response")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {
            "success": True,
            "data": [SAMPLE_PAYLOAD.model_dump()],
            "meta": {"offset": 0, "limit": 10, "total": 1},
        }


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
