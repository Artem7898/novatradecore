"""Shared test data; pytest-django owns application and database initialization."""

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from asgiref.sync import sync_to_async
from django.core.cache import cache
from django.db import connections
from pytest_django.plugin import DjangoDbBlocker


@pytest_asyncio.fixture(autouse=True)
async def close_async_database_connections(
    request: pytest.FixtureRequest,
    django_db_blocker: DjangoDbBlocker,
) -> AsyncIterator[None]:
    """Close ORM connections owned by the async adapter's worker thread.

    Django's synchronous test teardown cannot see that thread-local connection.
    Leaving it open prevents PostgreSQL from dropping the isolated test database.
    """
    yield
    if request.node.get_closest_marker("django_db") is not None:
        with django_db_blocker.unblock():
            await sync_to_async(connections.close_all, thread_sensitive=True)()


@pytest.fixture(autouse=True)
def isolated_cache() -> Iterator[None]:
    """Prevent authenticated rate-limit counters leaking between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def trade_payload() -> dict[str, str]:
    return {
        "symbol": "SOL/USDT",
        "side": "BUY",
        "price": "150.250000000",
        "quantity": "10.500000000",
        "exchange_id": "binance",
        "trade_id": "trade-001",
    }


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token-for-novatradecore-tests-0123456789"}
