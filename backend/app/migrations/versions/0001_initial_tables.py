"""Initial tables: child profile, characters, stories and the story-character link.

Revision ID: 0001
Revises: 
Create Date: 2026-11-27 21:57:08.854191
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401  (autogenerate uses sqlmodel's column types)
from alembic import op

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('character',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('type', sa.Enum('family', 'original', 'folklore', 'latte_monster', 'custom', name='charactertype'), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('traits', sa.JSON(), nullable=True),
    sa.Column('rules', sa.JSON(), nullable=True),
    sa.Column('image_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('childprofile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('age', sa.Integer(), nullable=False),
    sa.Column('favourite_things', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('story',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sa.Enum('idea', 'planned', 'written', 'read', name='storystatus'), nullable=False),
    sa.Column('text', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('word_count', sa.Integer(), nullable=True),
    sa.Column('reading_minutes', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('storycharacterlink',
    sa.Column('story_id', sa.Integer(), nullable=False),
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['character.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['story_id'], ['story.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('story_id', 'character_id')
    )


def downgrade() -> None:
    op.drop_table('storycharacterlink')
    op.drop_table('story')
    op.drop_table('childprofile')
    op.drop_table('character')
    # Postgres keeps enum types after their tables are dropped.
    sa.Enum(name='storystatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='charactertype').drop(op.get_bind(), checkfirst=True)
