from collections.abc import AsyncIterator
from typing import Final

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

pytest_plugins: Final[tuple[str, ...]] = ("tests.fixtures.responses",)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the test app."""

    transport = ASGITransport(app=app, raise_app_exceptions=False)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
