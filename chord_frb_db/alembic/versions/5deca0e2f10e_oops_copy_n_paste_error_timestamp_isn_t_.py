"""oops, copy-n-paste error, timestamp isn't part of the primary key

Revision ID: 5deca0e2f10e
Revises: ee3ce9520755
Create Date: 2024-09-16 20:13:20.019408

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5deca0e2f10e'
down_revision: Union[str, None] = 'ee3ce9520755'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
