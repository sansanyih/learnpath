"""Test bootstrap: set a throwaway database before importing the app."""

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ.setdefault("JWT_SECRET", "test-secret-0123456789abcdef0123456789")

from app.db.database import engine  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="session", autouse=True)
def _cleanup_db():
    yield
    db_file = Path(__file__).resolve().parents[1] / "test.db"
    if db_file.exists():
        try:
            db_file.unlink()
        except PermissionError:
            # Windows keeps the sqlite file locked until the engine is GC'd; harmless.
            pass
