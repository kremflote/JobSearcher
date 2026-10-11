"""job_sources: detail retry bookkeeping (Finn ad pages, ARCHITECTURE §4.2)

Revision ID: 7c3e9a1f4b20
Revises: 231dc362215e
Create Date: 2026-10-10 22:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c3e9a1f4b20'
down_revision: Union[str, Sequence[str], None] = '231dc362215e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('job_sources') as batch_op:
        batch_op.add_column(sa.Column('detail_attempts', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('detail_next_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('job_sources') as batch_op:
        batch_op.drop_column('detail_next_at')
        batch_op.drop_column('detail_attempts')
