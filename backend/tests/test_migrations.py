from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlmodel import SQLModel

from app import models  # noqa: F401
from app.db import create_tables, migrate


def test_migrations_create_every_table(engine):
    migrate(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"childprofile", "character", "story", "storycharacterlink", "alembic_version"} <= tables


def test_migrations_match_the_models(engine):
    """Fails when a model changes without a migration: run
    `alembic revision --autogenerate -m "..."` from backend/ to add one."""
    migrate(engine)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), SQLModel.metadata)
    assert differences == []


def test_migrate_is_safe_to_run_twice(engine):
    migrate(engine)
    migrate(engine)


def test_database_made_before_migrations_is_adopted(engine):
    create_tables(engine)  # how the app made tables before Alembic
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO childprofile (name, age, favourite_things) VALUES ('Mira', 3, '[]')"))

    migrate(engine)

    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"
        assert connection.execute(text("SELECT name FROM childprofile")).scalar() == "Mira"
