"""Database connectivity and async session management for SQLAlchemy."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engines: dict[str, tuple[AsyncEngine, async_sessionmaker[AsyncSession]]] = {}


def create_engine_and_session(
    database_url: str | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create or retrieve cached async SQLAlchemy engine and session factory."""
    url = database_url or get_settings().DATABASE_URL
    if url not in _engines:
        engine = create_async_engine(
            url,
            echo=False,
            future=True,
        )
        session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        _engines[url] = (engine, session_factory)
    return _engines[url]


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing transactional async database sessions."""
    _, session_factory = create_engine_and_session()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
