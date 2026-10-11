"""agent_runs: fallback_from (LLM fallback, ARCHITECTURE §8.1)

Revision ID: b4d2e8f1a903
Revises: 7c3e9a1f4b20
Create Date: 2026-10-11 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b4d2e8f1a903'
down_revision: Union[str, Sequence[str], None] = '7c3e9a1f4b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('agent_runs') as batch_op:
        batch_op.add_column(sa.Column('fallback_from', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('agent_runs') as batch_op:
        batch_op.drop_column('fallback_from')
