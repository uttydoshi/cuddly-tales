from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlmodel import SQLModel

from app import models  # noqa: F401
from app.db import migrate


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


def _upgrade_to(engine, revision):
    from alembic import command
    from alembic.config import Config

    from app.db import MIGRATIONS_DIR

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def _head() -> str:
    from alembic.script import ScriptDirectory

    from app.db import MIGRATIONS_DIR

    return ScriptDirectory(str(MIGRATIONS_DIR)).get_current_head()


def test_database_made_before_migrations_is_adopted(engine):
    # Before Alembic, the app made the tables directly: the shape of revision 0001,
    # with no alembic_version table.
    _upgrade_to(engine, "0001")
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO childprofile (name, age, favourite_things) VALUES ('Mira', 3, '[]')"))

    migrate(engine)

    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar() == _head()
        assert connection.execute(text("SELECT name FROM childprofile")).scalar() == "Mira"


def test_stories_written_before_the_bedtime_flag_become_bedtime_stories(engine):
    _upgrade_to(engine, "0001")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO story (title, status, created_at) VALUES ('Old one', 'written', '2026-11-20 08:00:00')"))

    migrate(engine)

    with engine.connect() as connection:
        assert connection.execute(text("SELECT bedtime FROM story WHERE title = 'Old one'")).scalar() in (1, True)
