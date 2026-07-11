"""
Test fixtures.

The session-scoped migration fixture runs the real `alembic upgrade head`
against the test database — this doubles as a regression test that the
migration chain works on an empty database.
"""

import pytest

from app.migrate import main as run_migrations


@pytest.fixture(scope="session")
def apply_migrations():
    run_migrations()
