"""A story is verified by a parent, not "read": the parent's sign-off before reading it to their child.

The status value read becomes verified, and read_at becomes verified_at. On Postgres the status is a
native enum type, so the value is renamed in the type; on SQLite it's plain text.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-28 17:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD = sa.Enum('idea', 'planned', 'written', 'read', name='storystatus')
NEW = sa.Enum('idea', 'planned', 'written', 'verified', name='storystatus')


def _rename_status(old: str, new: str, old_type: sa.Enum, new_type: sa.Enum) -> None:
    if op.get_bind().dialect.name == 'postgresql':
        # A native enum: rename the value in the type itself.
        op.execute(sa.text(f"ALTER TYPE storystatus RENAME VALUE '{old}' TO '{new}'"))
        return
    # Elsewhere the enum is text sized to its longest value ("verified" is longer than any old one).
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.alter_column('status', existing_type=old_type, type_=new_type, existing_nullable=False)
    op.execute(sa.text(f"UPDATE story SET status = '{new}' WHERE status = '{old}'"))


def upgrade() -> None:
    _rename_status('read', 'verified', OLD, NEW)
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.alter_column('read_at', new_column_name='verified_at')


def downgrade() -> None:
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.alter_column('verified_at', new_column_name='read_at')
    _rename_status('verified', 'read', NEW, OLD)
