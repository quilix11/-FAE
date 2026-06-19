"""Add version_id and max_capacity

Revision ID: f381fe8f3005
Revises: 3cd29cb961e8
Create Date: 2026-06-18 13:00:47.850750

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f381fe8f3005'
down_revision: Union[str, Sequence[str], None] = '3cd29cb961e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('zones', sa.Column('version_id', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('machines', sa.Column('max_capacity', sa.Integer(), nullable=False, server_default='10'))
    op.add_column('machines', sa.Column('version_id', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('machines', 'version_id')
    op.drop_column('machines', 'max_capacity')
    op.drop_column('zones', 'version_id')
