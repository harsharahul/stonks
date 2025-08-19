"""add_timestamp_columns_to_articles

Revision ID: 0afb1c406f1d
Revises: 4c88dcbd65b5
Create Date: 2025-08-18 22:33:05.613707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0afb1c406f1d'
down_revision: Union[str, None] = '4c88dcbd65b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add timestamp columns to articles table
    op.add_column('articles', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.add_column('articles', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()))


def downgrade() -> None:
    # Remove timestamp columns from articles table
    op.drop_column('articles', 'updated_at')
    op.drop_column('articles', 'created_at')
