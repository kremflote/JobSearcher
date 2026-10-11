"""draft_messages: style_rule, style_rule_saved_at ("Lagre som stilregel", ARCHITECTURE §7.2)

Revision ID: e2a9c4d7b315
Revises: c7e1f5a2d814
Create Date: 2026-10-11 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e2a9c4d7b315'
down_revision: Union[str, Sequence[str], None] = 'c7e1f5a2d814'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('draft_messages') as batch_op:
        batch_op.add_column(sa.Column('style_rule', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('style_rule_saved_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('draft_messages') as batch_op:
        batch_op.drop_column('style_rule_saved_at')
        batch_op.drop_column('style_rule')
