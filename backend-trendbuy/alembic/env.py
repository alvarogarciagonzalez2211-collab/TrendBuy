import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.database import Base  # noqa: E402


config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: migrations run in-process at FastAPI startup
    # (see models/database.py::init_db), and fileConfig's default of True would
    # silently disable uvicorn's own loggers (uvicorn.error/uvicorn.access) right
    # after migrating, swallowing every request log and error traceback from then on.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# The DATABASE_URL env var (same one models/database.py reads) always wins over
# whatever placeholder is in alembic.ini, so `alembic upgrade head` works out of
# the box both from the CLI and from the programmatic call in init_db().
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://trendbuy:trendbuy@localhost:5432/trendbuy",
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
