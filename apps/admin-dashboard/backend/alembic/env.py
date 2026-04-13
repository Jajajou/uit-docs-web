"""Alembic env.py for workspace store migrations.

Reads WORKSPACE_DATABASE_URL from the environment (via api.config)
and uses the same Base metadata that workspace_store.py defines.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the backend package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.config import settings  # noqa: E402
from api.services.workspace_store import Base  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url from env var
effective_url = os.getenv("WORKSPACE_DATABASE_URL") or settings.WORKSPACE_DATABASE_URL
config.set_main_option("sqlalchemy.url", effective_url)


def run_migrations_offline() -> None:
    """Run migrations in --sql mode (emit SQL to stdout)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
