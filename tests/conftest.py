from __future__ import annotations

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "15432")
os.environ.setdefault("POSTGRES_DB", "securedocvault_test")
os.environ.setdefault("POSTGRES_USER", "sdv")
os.environ.setdefault("POSTGRES_PASSWORD", "vault_secret_test")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "16379")
os.environ.setdefault("REDIS_PASSWORD", "changeme")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:19000")
os.environ.setdefault("MINIO_ROOT_USER", "minioadmin")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "minioadmin")
os.environ.setdefault("MINIO_BUCKET_DOCUMENTS", "vault-test")
os.environ.setdefault("PASETO_SECRET_KEY", "a" * 32)


def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests that require external services.",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--integration"):
        skip_integration = pytest.mark.skip(reason="Pass --integration to run")
        for item in items:
            if "integration" in item.keywords or "requires_db" in item.keywords:
                item.add_marker(skip_integration)


@pytest_asyncio.fixture(scope="session")
async def app():
    from src.main import app as _app
    return _app


@pytest_asyncio.fixture()
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
