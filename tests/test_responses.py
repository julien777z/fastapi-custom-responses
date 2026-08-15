from http import HTTPStatus

from httpx import AsyncClient

from tests.conftest import SAMPLE_PAYLOAD


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
