"""Alembic environment. The DB URL comes from DATA_DIR (jobsearcher.config)."""

from alembic import context
from sqlmodel import SQLModel

import jobsearcher.db.models  # noqa: F401  (registers tables)
from jobsearcher.db.session import get_engine

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=str(get_engine().url),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    with get_engine().connect() as connection:
        _run(connection)
        connection.commit()


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
