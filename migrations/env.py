import asyncio
import sys
from importlib import import_module
from importlib.util import find_spec
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import Connection, pool, text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.config import config
from app.core.modules import MODULES
from app.modules.db import Base

for _spec in MODULES:
    _found = find_spec(_spec.path)
    if _found and _found.origin and (Path(_found.origin).parent / "models.py").exists():
        import_module(f"{_spec.path}.models")

al_config = context.config
if al_config.config_file_name is not None:
    fileConfig(al_config.config_file_name)

target_metadata = Base.metadata
MIGRATION_LOCK = 7_302_116_711


def render_item(type_, obj, autogen_context):
    # fastapi-users' GUID is a plain UUID column in PostgreSQL: render it without the import
    if type_ == "type" and type(obj).__name__ == "GUID":
        return "sa.Uuid()"
    return False


def do_run_migrations(connection: Connection) -> None:
    """Under a PostgreSQL lock: replicas that start together migrate one after another,
    and the later ones find the database up to date."""
    locked = connection.dialect.name == "postgresql"
    if locked:
        connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK})
        connection.commit()
    try:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()
    finally:
        if locked:
            connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK})
            connection.commit()


async def run_migrations_online() -> None:
    connectable = create_async_engine(config.DATABASE_URL, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)


if context.is_offline_mode():
    context.configure(
        url=config.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_migrations_online())
