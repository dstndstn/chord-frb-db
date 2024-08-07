"""set some columns optional

Revision ID: 0f5d47b5a840
Revises: 6793bd1ef4d3
Create Date: 2024-06-11 14:35:28.266661

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f5d47b5a840'
down_revision: Union[str, None] = '6793bd1ef4d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('event', 'best_beam',
               existing_type=sa.SMALLINT(),
               nullable=True)
    op.alter_column('event', 'best_snr',
               existing_type=sa.REAL(),
               nullable=True)
    op.alter_column('event', 'total_snr',
               existing_type=sa.REAL(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('event', 'total_snr',
               existing_type=sa.REAL(),
               nullable=False)
    op.alter_column('event', 'best_snr',
               existing_type=sa.REAL(),
               nullable=False)
    op.alter_column('event', 'best_beam',
               existing_type=sa.SMALLINT(),
               nullable=False)
    # ### end Alembic commands ###
