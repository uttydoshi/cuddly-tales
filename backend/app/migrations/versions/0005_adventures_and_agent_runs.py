"""Adventures and the agent: plot cards, adventures, agent runs and their steps; stories get a night.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-28 13:11:30.812815
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401  (autogenerate uses sqlmodel's column types)
from alembic import op

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('adventure',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('premise', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('nights', sa.Integer(), nullable=False),
    sa.Column('bedtime', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('agentrun',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('goal', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('trigger', sa.String(length=20), nullable=False),
    sa.Column('nights', sa.Integer(), nullable=True),
    sa.Column('bedtime', sa.Boolean(), nullable=False),
    sa.Column('theme', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('character_ids', sa.JSON(), nullable=True),
    sa.Column('adventure_id', sa.Integer(), nullable=True),
    sa.Column('error', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['adventure_id'], ['adventure.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('agentstep',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('tool', sa.String(length=40), nullable=False),
    sa.Column('label', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('result', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('ok', sa.Boolean(), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['agentrun.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('agentstep', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_agentstep_run_id'), ['run_id'], unique=False)

    op.create_table('plotcard',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('story_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('text', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['story_id'], ['story.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('plotcard', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plotcard_story_id'), ['story_id'], unique=False)

    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.add_column(sa.Column('adventure_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('night', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_story_adventure_id', 'adventure', ['adventure_id'], ['id'], ondelete='CASCADE')



def downgrade() -> None:
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.drop_constraint('fk_story_adventure_id', type_='foreignkey')
        batch_op.drop_column('night')
        batch_op.drop_column('adventure_id')

    with op.batch_alter_table('plotcard', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_plotcard_story_id'))

    op.drop_table('plotcard')
    with op.batch_alter_table('agentstep', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_agentstep_run_id'))

    op.drop_table('agentstep')
    op.drop_table('agentrun')
    op.drop_table('adventure')
