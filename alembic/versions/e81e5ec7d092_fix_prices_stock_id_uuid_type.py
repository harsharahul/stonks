"""fix_prices_stock_id_uuid_type

Revision ID: e81e5ec7d092
Revises: 7b7a9f6fdcd6
Create Date: 2026-02-15 00:24:43.554334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'e81e5ec7d092'
down_revision: Union[str, None] = '7b7a9f6fdcd6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix prices.stock_id type from VARCHAR to UUID
    # The USING clause converts existing VARCHAR values to UUID
    op.execute('''
        ALTER TABLE prices
        ALTER COLUMN stock_id TYPE UUID
        USING stock_id::uuid;
    ''')


def downgrade() -> None:
    # Revert UUID back to VARCHAR (not recommended, but for completeness)
    op.execute('''
        ALTER TABLE prices
        ALTER COLUMN stock_id TYPE VARCHAR
        USING stock_id::varchar;
    ''')
