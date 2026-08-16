from http import HTTPStatus

import pytest
from httpx import AsyncClient

from fastapi_custom_responses import PaginatedResponse
from tests.conftest import SAMPLE_PAYLOAD, ValidationPayload


class TestSuccessEnvelopes:
    """Tests for the shape of the success response envelopes."""

    client: AsyncClient

    async def test_response_carries_only_success_and_data(self) -> None:
        """Test that a data-carrying response emits no fields beyond success and data."""

        response = await self.client.get("/response-with-data")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"success": True, "data": SAMPLE_PAYLOAD.model_dump()}

    async def test_success_response_carries_only_success(self) -> None:
        """Test that a payload-free response emits nothing but success."""

        response = await self.client.get("/success-response")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"success": True}

    async def test_paginated_response_carries_data_and_meta(self) -> None:
        """Test that a paginated response emits its data and pagination metadata."""

        response = await self.client.get("/paginated-response")

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

        assert page.data == []
        assert page.meta.total == 57

    def test_bounds_cannot_be_passed_positionally(self) -> None:
        """Test that the three bounds are keyword-only and cannot be transposed by position."""

        with pytest.raises(TypeError):
            # pylint: disable-next=too-many-function-args
            PaginatedResponse.build_page([SAMPLE_PAYLOAD], 20, 10, 57)

    def test_parametrized_page_validates_its_items(self) -> None:
        """Test that a parametrized paginated response still validates the items it is given."""

        page = PaginatedResponse[ValidationPayload].build_page([SAMPLE_PAYLOAD], offset=0, limit=10, total=1)

        assert page.data == [SAMPLE_PAYLOAD]
