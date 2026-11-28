"""Adventures are told in chapters, not nights (an adventure can be for any time of day).

Renames story.night -> chapter, adventure.nights -> chapter_count and agentrun.nights ->
chapter_count, and updates what's already saved to match: the run kind next_night, and the
goals and step labels the planner page shows.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-28 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# What the planner wrote; only words it chose itself, never the model's own messages.
TOOL_STEPS = "tool <> 'message'"


def _rename(old: str, new: str, kind_old: str, kind_new: str) -> None:
    op.execute(sa.text(f"UPDATE agentrun SET kind = '{kind_new}' WHERE kind = '{kind_old}'"))
    op.execute(sa.text(f"UPDATE agentrun SET goal = REPLACE(goal, '-{old} adventure', '-{new} adventure')"))
    op.execute(sa.text(f"UPDATE agentrun SET goal = REPLACE(goal, 'Write {old} ', 'Write {new} ')"))
    # Labels are fixed phrases ("Write night 1"); results also hold story titles, so only the
    # exact phrases the planner wrote change there ("Planned 3 nights of", "Saved night 1,").
    op.execute(sa.text(f"UPDATE agentstep SET label = REPLACE(label, ' {old}s', ' {new}s') WHERE {TOOL_STEPS}"))
    op.execute(sa.text(f"UPDATE agentstep SET label = REPLACE(label, ' {old} ', ' {new} ') WHERE {TOOL_STEPS}"))
    for phrase_old, phrase_new in ((f" {old}s of ", f" {new}s of "), (f"Saved {old} ", f"Saved {new} "), (f" {old}s written", f" {new}s written")):
        op.execute(sa.text(f"UPDATE agentstep SET result = REPLACE(result, '{phrase_old}', '{phrase_new}') WHERE {TOOL_STEPS}"))


def upgrade() -> None:
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.alter_column('night', new_column_name='chapter')
    with op.batch_alter_table('adventure', schema=None) as batch_op:
        batch_op.alter_column('nights', new_column_name='chapter_count')
    with op.batch_alter_table('agentrun', schema=None) as batch_op:
        batch_op.alter_column('nights', new_column_name='chapter_count')
    _rename('night', 'chapter', 'next_night', 'next_chapter')


def downgrade() -> None:
    _rename('chapter', 'night', 'next_chapter', 'next_night')
    with op.batch_alter_table('agentrun', schema=None) as batch_op:
        batch_op.alter_column('chapter_count', new_column_name='nights')
    with op.batch_alter_table('adventure', schema=None) as batch_op:
        batch_op.alter_column('chapter_count', new_column_name='nights')
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.alter_column('chapter', new_column_name='night')
