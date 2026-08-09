"""Postgres connection pool.

Plain SQL over asyncpg. No `supabase-js`, no ORM. The database is ordinary Postgres, so this
code moves to any Postgres host unchanged; that portability is the reason Supabase was chosen
without being locked into.
"""

import asyncpg
from pgvector.asyncpg import register_vector

from winchat_api.config import get_settings


class DatabaseNotConfigured(RuntimeError):
    """DATABASE_URL is missing. Raised instead of failing deep inside a query."""


async def _init_connection(connection: asyncpg.Connection) -> None:
    """Teach asyncpg the pgvector type so Python lists map to `vector` columns."""
    await register_vector(connection)


async def create_pool(
    *, min_size: int = 1, max_size: int = 10, with_vector_type: bool = True
) -> asyncpg.Pool:
    """Open a pool.

    `with_vector_type=False` is for the migration runner: the `vector` type does not exist until
    the first migration creates the extension, and registering a codec for a type that is not
    there yet fails the connection before it can fix itself.
    """
    settings = get_settings()
    if not settings.database_url:
        raise DatabaseNotConfigured("DATABASE_URL is not set")

    return await asyncpg.create_pool(
        settings.database_url,
        min_size=min_size,
        max_size=max_size,
        init=_init_connection if with_vector_type else None,
        # Recycle idle connections before the server does. Supabase's pooler closes
        # connections that sit idle, and asyncpg does not find out until it hands one to a
        # query, which then dies mid-statement with ConnectionDoesNotExistError.
        max_inactive_connection_lifetime=60.0,
        # A dead connection can still be handed out inside the race window above. One
        # retry on acquire turns a user-visible 500 into an invisible reconnect.
        command_timeout=60.0,
    )
