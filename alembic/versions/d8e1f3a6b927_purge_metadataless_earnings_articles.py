"""purge legacy earnings articles that lost their metadata

Earnings ingestion passed ``metadata=`` to Article() instead of
``article_metadata=`` — SQLAlchemy silently dropped the payload, so every
earnings article persisted with NULL metadata. In prod (no Alpha Vantage key
configured) those rows also carried RANDOM mock earnings dates in their
titles. They are unidentifiable as mock vs real and unusable downstream;
delete them. Real dates repopulate from the provider on the next nightly run.

Revision ID: d8e1f3a6b927
Revises: c7d4e9f2a815
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d8e1f3a6b927"
down_revision: Union[str, None] = "c7d4e9f2a815"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM articles WHERE url LIKE 'earnings://%' AND article_metadata IS NULL"
    )


def downgrade() -> None:
    pass  # deleted rows were fabricated/unusable; nothing to restore
