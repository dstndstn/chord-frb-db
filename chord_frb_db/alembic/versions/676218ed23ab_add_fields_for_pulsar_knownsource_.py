"""add fields for pulsar KnownSource entries

Revision ID: 676218ed23ab
Revises: 5deca0e2f10e
Create Date: 2025-01-20 22:05:19.376257

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '676218ed23ab'
down_revision: Union[str, None] = '5deca0e2f10e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('known_source', sa.Column('source_type', sa.String(length=32), nullable=False))
    op.add_column('known_source', sa.Column('origin', sa.String(length=32), nullable=False))
    op.add_column('known_source', sa.Column('ra_error', sa.REAL(), nullable=True))
    op.add_column('known_source', sa.Column('dec_error', sa.REAL(), nullable=True))
    op.add_column('known_source', sa.Column('dm_error', sa.REAL(), nullable=True))
    op.add_column('known_source', sa.Column('s400', sa.REAL(), nullable=True))
    op.add_column('known_source', sa.Column('s400_error', sa.REAL(), nullable=True))
    op.add_column('known_source', sa.Column('s1400', sa.REAL(), nullable=True))
    op.add_column('known_source', sa.Column('s1400_error', sa.REAL(), nullable=True))
    op.alter_column('known_source', 'ra',
               existing_type=sa.REAL(),
               nullable=False)
    op.alter_column('known_source', 'dec',
               existing_type=sa.REAL(),
               nullable=False)
    op.alter_column('known_source', 'dm',
               existing_type=sa.REAL(),
               nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('known_source', 'dm',
               existing_type=sa.REAL(),
               nullable=True)
    op.alter_column('known_source', 'dec',
               existing_type=sa.REAL(),
               nullable=True)
    op.alter_column('known_source', 'ra',
               existing_type=sa.REAL(),
               nullable=True)
    op.drop_column('known_source', 's1400_error')
    op.drop_column('known_source', 's1400')
    op.drop_column('known_source', 's400_error')
    op.drop_column('known_source', 's400')
    op.drop_column('known_source', 'dm_error')
    op.drop_column('known_source', 'dec_error')
    op.drop_column('known_source', 'ra_error')
    op.drop_column('known_source', 'origin')
    op.drop_column('known_source', 'source_type')
    # ### end Alembic commands ###
