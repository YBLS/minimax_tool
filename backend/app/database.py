"""asyncpg connection pool + tiny query helpers."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import asyncpg

from app.config import get_settings

logger = logging.getLogger(__name__)


class Database:
    """Singleton wrapper around an asyncpg pool."""

    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def init(cls) -> None:
        if cls._pool is not None:
            return
        s = get_settings()
        # first create the database if missing
        try:
            conn = await asyncpg.connect(dsn=s.db_dsn)
            await conn.close()
        except asyncpg.InvalidCatalogNameError:
            logger.info("Database %s not found, creating...", s.db_name)
            admin = await asyncpg.connect(dsn=s.db_dsn_no_db)
            try:
                await admin.execute(f'CREATE DATABASE "{s.db_name}"')
            finally:
                await admin.close()
            conn = await asyncpg.connect(dsn=s.db_dsn)
            await conn.close()

        cls._pool = await asyncpg.create_pool(
            dsn=s.db_dsn,
            min_size=1,
            max_size=10,
            command_timeout=60,
            init=_init_connection,
        )
        logger.info("Postgres pool ready (min=1, max=10)")

    @classmethod
    async def close(cls) -> None:
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    def pool(cls) -> asyncpg.Pool:
        if cls._pool is None:
            raise RuntimeError("Database pool is not initialised. Call Database.init() first.")
        return cls._pool


async def _init_connection(conn: asyncpg.Connection) -> None:
    """No-op. JSONB values are handled explicitly with ::jsonb casts and
    json.dumps/json.loads at the call sites. Installing a codec here would
    double-encode pre-serialized JSON strings, so we leave the column types
    as their native text representation and let the SQL casts do the work.
    """
    return


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    return await Database.pool().fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> Optional[asyncpg.Record]:
    return await Database.pool().fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    return await Database.pool().fetchval(query, *args)


async def execute(query: str, *args: Any) -> str:
    return await Database.pool().execute(query, *args)
