"""Running queries as the signed-in user, so Row Level Security actually applies.

The pool connects as a privileged role. Issuing a query on it directly bypasses every policy in
the schema.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg


@asynccontextmanager
async def user_scoped(pool: asyncpg.Pool, user_id: str) -> AsyncIterator[asyncpg.Connection]:
    """Yield a connection inside a transaction bound to `user_id`."""
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute("select set_config('role', 'authenticated', true)")
        await connection.execute(
            "select set_config('request.jwt.claims', $1, true)",
            json.dumps({"sub": user_id, "role": "authenticated"}),
        )
        yield connection
