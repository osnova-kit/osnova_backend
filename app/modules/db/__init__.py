from fastapi import FastAPI

from .database import (
    Base,
    JSONData,
    app_session,
    engine,
    get_async_session,
    standalone_session,
    utc_now,
)

__all__ = [
    "Base",
    "JSONData",
    "app_session",
    "engine",
    "get_async_session",
    "register",
    "standalone_session",
    "utc_now",
]


def register(app: FastAPI):
    from sqlalchemy import text

    from app.core.readiness import add_check

    async def database() -> None:
        async with app_session(app) as session:
            await session.execute(text("SELECT 1"))

    add_check("database", database)

    async def shutdown() -> None:
        if engine is not None:
            await engine.dispose()

    return shutdown
