"""Stories get a bedtime flag: bedtime stories end calm and sleepy, others are for any time.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-27 23:56:51.615224
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401  (autogenerate uses sqlmodel's column types)
from alembic import op

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A default, so the column can be added to a table that already has stories.
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bedtime', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Every story written before this change was written as a bedtime story.
    op.execute(sa.text('UPDATE story SET bedtime = TRUE'))


def downgrade() -> None:
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.drop_column('bedtime')
