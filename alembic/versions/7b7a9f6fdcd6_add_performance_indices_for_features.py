"""add_performance_indices_for_features

Revision ID: 7b7a9f6fdcd6
Revises: 265a67cf79e8
Create Date: 2026-02-15 00:22:30.724699

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b7a9f6fdcd6'
down_revision: Union[str, None] = '265a67cf79e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index for prices table - improves momentum feature calculations
    # Composite index on (stock_id, ts) for efficient time-series queries
    op.create_index(
        'idx_prices_stock_ts',
        'prices',
        ['stock_id', 'ts'],
        unique=False
    )

    # Expression index for earnings events (most common metadata query)
    # Note: article_metadata is JSON type (not JSONB), so we use expression indices
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_articles_metadata_event_type
        ON articles ((article_metadata->>'event_type'));
    ''')

    # Expression index for source filtering (WSB, etc.)
    op.execute('''
        CREATE INDEX IF NOT EXISTS idx_articles_metadata_source
        ON articles ((article_metadata->>'source'));
    ''')

    # Index for published_at + tickers (used in most feature calculations)
    op.create_index(
        'idx_articles_published_tickers',
        'articles',
        ['published_at'],
        unique=False,
        postgresql_where=sa.text("tickers IS NOT NULL")
    )


def downgrade() -> None:
    # Drop indices in reverse order
    op.drop_index('idx_articles_published_tickers', table_name='articles')
    op.execute('DROP INDEX IF EXISTS idx_articles_metadata_source;')
    op.execute('DROP INDEX IF EXISTS idx_articles_metadata_event_type;')
    op.drop_index('idx_prices_stock_ts', table_name='prices')
