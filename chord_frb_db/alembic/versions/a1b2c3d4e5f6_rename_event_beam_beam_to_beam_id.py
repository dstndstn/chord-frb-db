"""rename event_beam.beam to beam_id

Revision ID: a1b2c3d4e5f6
Revises: 26a9940610b0
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '26a9940610b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('event_beam', 'beam', new_column_name='beam_id')


def downgrade() -> None:
    op.alter_column('event_beam', 'beam_id', new_column_name='beam')
