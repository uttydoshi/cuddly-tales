"""Alembic environment.

The app runs migrations itself at startup (app.db.migrate), passing in its own
connection. The `alembic` command line (from backend/, using alembic.ini)
connects to DATABASE_URL instead, e.g. to create a new revision:

    .venv/bin/alembic revision --autogenerate -m "add plot cards"
"""

from alembic import context
from sqlmodel import SQLModel

from app import models  # noqa: F401  (registers the tables on SQLModel.metadata)

target_metadata = SQLModel.metadata


def run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite can't ALTER most things; batch mode rebuilds the table instead.
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline (SQL script) migrations are not set up for this project.")

shared_connection = context.config.attributes.get("connection")
if shared_connection is not None:
    run(shared_connection)
else:
    from app.config import get_settings
    from app.db import make_engine

    with make_engine(get_settings().database_url).connect() as connection:
        run(connection)
        connection.commit()
