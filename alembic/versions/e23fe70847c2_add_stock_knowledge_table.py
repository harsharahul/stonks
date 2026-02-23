"""add_stock_knowledge_table

Revision ID: e23fe70847c2
Revises: e81e5ec7d092
Create Date: 2026-02-22 12:25:37.620331

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e23fe70847c2'
down_revision: Union[str, None] = 'e81e5ec7d092'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stock_knowledge',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('ticker', sa.String(length=10), nullable=False),
        sa.Column('narrative', sa.Text(), nullable=True),
        sa.Column('key_events', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sentiment_trend', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('article_count_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_stock_knowledge_ticker'), 'stock_knowledge', ['ticker'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_stock_knowledge_ticker'), table_name='stock_knowledge')
    op.drop_table('stock_knowledge')
