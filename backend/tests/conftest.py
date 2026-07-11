"""
Test fixtures.

The session-scoped migration fixture runs the real `alembic upgrade head`
against the test database — this doubles as a regression test that the
migration chain works on an empty database.
"""

import pytest

from app.database import engine
from app.migrate import main as run_migrations


@pytest.fixture(scope="session")
def apply_migrations():
    run_migrations()


@pytest.fixture(autouse=True)
async def dispose_engine_after_test():
    """
    pytest-asyncio gives every test its own event loop, but the app engine's
    pool would happily hand a connection created in a previous loop to the
    next test ("cannot perform operation: another operation is in progress").
    Disposing the pool after each test forces fresh connections per loop.
    """
    yield
    await engine.dispose()
