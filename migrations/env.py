"""Alembic entrypoint: secrets are mounted files, never checked-in URLs."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

from personal_brain_server.bootstrap.settings import read_secret_file


def _database_url() -> str:
    secret_path = os.environ.get("BRAIN_DATABASE_DSN_FILE")
    if not secret_path:
        raise RuntimeError("BRAIN_DATABASE_DSN_FILE is required for migrations")
    return read_secret_file(Path(secret_path)).get_secret_value()


def run_migrations_offline() -> None:
    context.configure(url=_database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
