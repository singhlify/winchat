"""Migration runner — applies the .sql files in `migrations/` in filename order.

Deliberately ~40 lines instead of Alembic. The schema is plain SQL that a reviewer can
read top to bottom, and Alembic's autogenerate buys nothing without an ORM model layer.
Each file runs inside a transaction and is recorded, so re-running is a no-op.

    uv run python -m winchat_api.db.migrate
"""

import asyncio
import logging

import asyncpg

from winchat_api.config import BACKEND_ROOT
from winchat_api.db.pool import create_pool

MIGRATIONS_DIR = BACKEND_ROOT / "migrations"

logger = logging.getLogger(__name__)


async def apply_migrations(connection: asyncpg.Connection) -> list[str]:
    """Apply any unapplied migrations. Returns the versions applied this run."""
    await connection.execute(
        """
        create table if not exists schema_migrations (
            version    text primary key,
            applied_at timestamptz not null default now()
        )
        """
    )
    rows = await connection.fetch("select version from schema_migrations")
    applied = {record["version"] for record in rows}

    newly_applied: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        async with connection.transaction():
            await connection.execute(path.read_text())
            await connection.execute(
                "insert into schema_migrations (version) values ($1)", version
            )
        newly_applied.append(version)

    return newly_applied


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    pool = await create_pool(max_size=2, with_vector_type=False)
    try:
        async with pool.acquire() as connection:
            applied = await apply_migrations(connection)
        if applied:
            logger.info("applied migrations: %s", ", ".join(applied))
        else:
            logger.info("schema already up to date")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
