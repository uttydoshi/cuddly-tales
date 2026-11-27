"""Stories get the result of the safety and age check: a status and the full report.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-28 10:04:17.271233
"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel  # noqa: F401  (autogenerate uses sqlmodel's column types)
from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

safety_status = sa.Enum('passed', 'rewritten', 'needs_review', 'approved', name='safetystatus')


def upgrade() -> None:
    # On Postgres an enum is its own type. Adding a column doesn't create it (making a table
    # does), so create it first. A no-op on SQLite.
    safety_status.create(op.get_bind(), checkfirst=True)
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.add_column(sa.Column('safety_status', safety_status, nullable=True))
        batch_op.add_column(sa.Column('safety_report', sa.JSON(), nullable=True))
    # Stories written before the check existed stay unchecked (NULL): nothing is made up for them.


def downgrade() -> None:
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.drop_column('safety_report')
        batch_op.drop_column('safety_status')
    safety_status.drop(op.get_bind(), checkfirst=True)
