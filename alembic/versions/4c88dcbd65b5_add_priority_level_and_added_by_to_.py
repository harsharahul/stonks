"""add_priority_level_and_added_by_to_stocks

Revision ID: 4c88dcbd65b5
Revises: c2526350b48a
Create Date: 2025-08-18 13:56:16.662749

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c88dcbd65b5'
down_revision: Union[str, None] = 'c2526350b48a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add priority_level and added_by columns to stocks table
    op.add_column('stocks', sa.Column('priority_level', sa.String(), nullable=True))
    op.add_column('stocks', sa.Column('added_by', sa.String(), nullable=True))
    
    # Set default values for existing rows
    op.execute("UPDATE stocks SET priority_level = 'normal' WHERE priority_level IS NULL")
    op.execute("UPDATE stocks SET added_by = 'system' WHERE added_by IS NULL")


def downgrade() -> None:
    # Remove the added columns
    op.drop_column('stocks', 'added_by')
    op.drop_column('stocks', 'priority_level')
