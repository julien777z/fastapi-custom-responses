from http import HTTPStatus

import pytest
from httpx import AsyncClient

from tests.conftest import (
    RAISED_ERROR_CASES,
    SECRET_TOKEN,
    RaisedErrorCase,
)


class TestErrorEnvelope:
    """Tests for the envelope every failing path renders."""

    @pytest.mark.parametrize(("case_name", "case"), RAISED_ERROR_CASES.items(), ids=RAISED_ERROR_CASES)
    async def test_renders_the_error_envelope(
        self, client: AsyncClient, case_name: str, case: RaisedErrorCase
    ) -> None:
        """Test that each failing path renders the envelope with its status and code."""

        response = await client.get(f"/raise/{case_name}")

        assert response.status_code == case.status_code
        assert response.json() == case.expected_body

    @pytest.mark.parametrize(
        ("method", "path", "status_code"),
        [
            ("GET", "/no-such-route", HTTPStatus.NOT_FOUND),
            ("POST", "/success-response", HTTPStatus.METHOD_NOT_ALLOWED),
        ],
        ids=["unknown_route", "wrong_method"],
    )
    async def test_a_routing_failure_renders_the_envelope(
        self, client: AsyncClient, method: str, path: str, status_code: HTTPStatus
    ) -> None:
        """Test that the errors the router raises itself render the envelope like any other."""

        response = await client.request(method, path)

        assert response.status_code == status_code
        assert response.json() == {"success": False, "error": status_code.phrase}

    async def test_the_headers_an_http_exception_carries_reach_the_client(self, client: AsyncClient) -> None:
        """Test that headers attached to an HTTP exception survive the envelope conversion."""

        response = await client.post("/success-response")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert response.headers["allow"] == "GET"

    async def test_a_model_that_fails_to_validate_reports_generically(self, client: AsyncClient) -> None:
        """Test that a model failing to validate inside the app never echoes what it was given."""

        response = await client.get("/invalid-model")

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert response.json() == {
            "success": False,
            "error": HTTPStatus.INTERNAL_SERVER_ERROR.phrase,
            "code": "internal_error",
        }
        assert SECRET_TOKEN not in response.text
