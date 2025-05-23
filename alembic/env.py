# alembic/env.py

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

import app.models  # noqa: F401 - Import all models so Alembic can detect schema changes
from alembic import context
from app.db.base import Base

# Alembic Config object, provides access to values within the .ini file
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target_metadata for 'autogenerate' support
target_metadata = Base.metadata


def get_url():
    """
    Return the sync database URL from the environment variable.
    This keeps credentials out of version control and makes migrations secure.
    """
    url = os.environ.get("DATABASE_URL_LOCAL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL_LOCAL is not set. Please export it before running Alembic."
        )
    return url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode. This configures the context with
    just a URL and not an Engine.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode. This creates an Engine and associates a connection.
    """
    url = get_url()
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
