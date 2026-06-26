"""empty message

Revision ID: ba192e91cc86
Revises: 676218ed23ab
Create Date: 2026-05-20 15:16:58.242943

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba192e91cc86'
down_revision: Union[str, None] = '676218ed23ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
