from http import HTTPStatus
from inspect import Parameter, signature

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from fastapi_custom_responses import PaginatedResponse, Response, SuccessResponse
from fastapi_custom_responses.models.responses import PaginationMeta
from tests.fixtures.models import ValidationPayload
from tests.fixtures.responses import SAMPLE_PAYLOAD


class TestResponseEnvelopes:
    """Tests for success response envelopes."""

    @pytest.mark.parametrize(
        ("path", "expected_body"),
        [
            ("/response-with-data", Response(success=True, data=SAMPLE_PAYLOAD)),
            ("/success-response", SuccessResponse(success=True)),
            (
                "/paginated-response",
                PaginatedResponse(
                    success=True, data=[SAMPLE_PAYLOAD], meta=PaginationMeta(offset=0, limit=10, total=1)
                ),
            ),
        ],
        ids=["with_data", "payload_free", "paginated"],
    )
    async def test_renders(
        self,
        client: AsyncClient,
        path: str,
        expected_body: Response[ValidationPayload] | SuccessResponse | PaginatedResponse[ValidationPayload],
    ) -> None:
        """Test that each success envelope emits its documented body and nothing more."""

        response = await client.get(path)

        assert response.status_code == HTTPStatus.OK
        assert response.json() == expected_body.model_dump(mode="json")

    @pytest.mark.parametrize(
        ("items", "offset"),
        [([SAMPLE_PAYLOAD], 20), ([], 90)],
        ids=["populated", "empty"],
    )
    def test_page_contents_and_bounds(self, items: list[ValidationPayload], offset: int) -> None:
        """Test that populated and empty pages preserve their items and pagination bounds."""

        page = PaginatedResponse.build_page(items, offset=offset, limit=10, total=57)

        assert page.model_dump() == {
            "success": True,
            "data": [item.model_dump() for item in items],
            "meta": {"offset": offset, "limit": 10, "total": 57},
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
