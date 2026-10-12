import os
import subprocess
import sys
import tempfile
from pathlib import Path

# --- environment must be set before the app is imported -------------------------------------------------
TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://societypass:societypass@localhost:5432/societypass_test")
_STORAGE_DIR = tempfile.mkdtemp(prefix="sp-test-storage-")
os.environ.update(
    ENV="test", DATABASE_URL=TEST_DB, STORAGE_BACKEND="local", LOCAL_STORAGE_DIR=_STORAGE_DIR,
    OTP_PROVIDER="console", OTP_RESEND_COOLDOWN_SECONDS="0", OTP_PER_PHONE_PER_HOUR="1000",
    OTP_PER_IP_PER_HOUR="100000", BACKGROUND_JOBS="false", API_PUBLIC_URL="http://test",
    JWT_SECRET="test-jwt-secret-test-jwt-secret-1234", QR_SECRET="test-qr-secret-test-qr-secret-1234",
)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.services.push import push  # noqa: E402
from app.services.storage import get_storage  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    """Build the schema with the real Alembic migrations (so migrations are tested too)."""
    env = {**os.environ}
    for cmd in (["downgrade", "base"], ["upgrade", "head"]):
        r = subprocess.run([sys.executable, "-m", "alembic", *cmd], cwd=BACKEND_DIR, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"alembic {cmd} failed:\n{r.stderr}")


@pytest_asyncio.fixture(autouse=True)
async def _clean_db():
    yield
    async with engine.begin() as conn:
        tables = (await conn.execute(text(
            "select tablename from pg_tables where schemaname='public' and tablename <> 'alembic_version'"))).scalars().all()
        await conn.execute(text("truncate table " + ", ".join(f'"{t}"' for t in tables) + " restart identity cascade"))
    limiter.reset()
    push.outbox.clear()
    get_storage().wipe()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
