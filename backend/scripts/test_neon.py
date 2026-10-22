"""Connect to Neon using .env.render and create tables."""

import asyncio
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

ROOT = Path(__file__).resolve().parents[2]
for line in (ROOT / ".env.render").read_text(encoding="utf-8").splitlines():
    if line.startswith("DATABASE_URL="):
        os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip()
        break

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.database import engine  # noqa: E402
from app.db.models import Base  # noqa: E402


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        count = await conn.scalar(
            text("select count(*) from information_schema.tables where table_schema='public'")
        )
    print("tables_created", count)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
