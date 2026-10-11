"""draft_messages: revision chat (FRONTEND §5.5, ARCHITECTURE §9)

Revision ID: c7e1f5a2d814
Revises: b4d2e8f1a903
Create Date: 2026-10-11 13:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c7e1f5a2d814'
down_revision: Union[str, Sequence[str], None] = 'b4d2e8f1a903'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'draft_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('text', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('draft_id', sa.Integer(), nullable=True),
        sa.Column('agent_run_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id']),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
        sa.ForeignKeyConstraint(['draft_id'], ['drafts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_draft_messages_application_id'), 'draft_messages', ['application_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_draft_messages_application_id'), table_name='draft_messages')
    op.drop_table('draft_messages')
