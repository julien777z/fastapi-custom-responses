from http import HTTPStatus
from inspect import Parameter, signature

import pytest
from httpx import AsyncClient

from fastapi_custom_responses import (
    DefaultErrorCode,
    ErrorResponse,
)
from tests.fixtures.models import RaisedErrorCase
from tests.fixtures.responses import (
    RAISED_ERROR_CASES,
    SECRET_TOKEN,
)


class TestErrorEnvelope:
    """Tests for normalized error responses."""

    @pytest.mark.parametrize(("case_name", "case"), RAISED_ERROR_CASES.items(), ids=RAISED_ERROR_CASES)
    async def test_renders_the_error_envelope(
        self, client: AsyncClient, case_name: str, case: RaisedErrorCase
    ) -> None:
        """Test that each failing path renders the envelope with its status and code."""

        response = await client.get(f"/raise/{case_name}")

        assert response.status_code == case.status_code
        assert response.json() == case.expected_body.model_dump(mode="json", exclude_none=True)

    @pytest.mark.parametrize(
        ("method", "path", "status_code"),
        [
            ("GET", "/no-such-route", HTTPStatus.NOT_FOUND),
            ("POST", "/success-response", HTTPStatus.METHOD_NOT_ALLOWED),
        ],
        ids=["unknown_route", "wrong_method"],
    )
    async def test_routing_failure(
        self, client: AsyncClient, method: str, path: str, status_code: HTTPStatus
    ) -> None:
        """Test that the errors the router raises itself render the envelope like any other."""

        response = await client.request(method, path)

        assert response.status_code == status_code
        assert response.json() == {"success": False, "error": status_code.phrase}

    async def test_http_headers(self, client: AsyncClient) -> None:
        """Test that headers attached to an HTTP exception survive the envelope conversion."""

        response = await client.post("/success-response")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert response.headers["allow"] == "GET"

    async def test_internal_validation_is_generic(self, client: AsyncClient) -> None:
        """Test that a model failing to validate inside the app never echoes what it was given."""

        response = await client.get("/invalid-model")

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert response.json() == {
            "success": False,
            "error": HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
            "code": DefaultErrorCode.INTERNAL_ERROR,
        }

        assert SECRET_TOKEN not in response.text

    def test_code_is_keyword_only(self) -> None:
        """Test that the error code can only be supplied by keyword."""

        assert signature(ErrorResponse).parameters["code"].kind is Parameter.KEYWORD_ONLY

    def test_missing_code_stays_absent(self) -> None:
        """Test that an error raised without a code carries none rather than restating its status."""

        assert ErrorResponse("boom", HTTPStatus.FORBIDDEN).code is None
