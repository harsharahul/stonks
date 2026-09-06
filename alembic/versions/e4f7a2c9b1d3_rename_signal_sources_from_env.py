"""rename signal source ids listed in SIGNAL_SOURCE_RENAMES

The tracked-figure plugins became generic, configurable sources with new ids.
A deployment that already holds signals, outcomes, and admin state under the
old ids sets ``SIGNAL_SOURCE_RENAMES`` (JSON object ``{old_id: new_id}``)
before upgrading so its track records carry across. With the variable unset
this revision is a no-op, which is what a fresh install wants.

Revision ID: e4f7a2c9b1d3
Revises: d8e1f3a6b927
Create Date: 2026-09-06
"""
import json
import os
from typing import Dict, Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4f7a2c9b1d3"
down_revision: Union[str, None] = "d8e1f3a6b927"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _renames() -> Dict[str, str]:
    raw = os.getenv("SIGNAL_SOURCE_RENAMES", "").strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("SIGNAL_SOURCE_RENAMES must be a JSON object of {old_id: new_id}")
    return {str(k): str(v) for k, v in data.items()}


def _apply(renames: Dict[str, str]) -> None:
    conn = op.get_bind()
    for old, new in renames.items():
        params = {"old": old, "new": new, "old_mv": f"plugin:{old}", "new_mv": f"plugin:{new}"}
        # Admin state: rename, or drop the old row when the new id already has one.
        conn.execute(
            sa.text(
                "UPDATE signal_source_states SET source_id = :new "
                "WHERE source_id = :old AND NOT EXISTS "
                "(SELECT 1 FROM signal_source_states s2 WHERE s2.source_id = :new)"
            ),
            params,
        )
        conn.execute(sa.text("DELETE FROM signal_source_states WHERE source_id = :old"), params)
        # Emitted signals: provenance column and the metadata attribution key.
        conn.execute(sa.text("UPDATE signals SET model_version = :new_mv WHERE model_version = :old_mv"), params)
        conn.execute(
            sa.text(
                "UPDATE signals SET signal_metadata = "
                "(signal_metadata::jsonb || jsonb_build_object('source_plugin', CAST(:new AS text)))::json "
                "WHERE signal_metadata IS NOT NULL AND signal_metadata->>'source_plugin' = :old"
            ),
            params,
        )
        # Scored outcomes: the per-source track record.
        conn.execute(sa.text("UPDATE signal_outcomes SET source = :new WHERE source = :old"), params)


def upgrade() -> None:
    renames = _renames()
    if renames:
        _apply(renames)


def downgrade() -> None:
    renames = _renames()
    if renames:
        _apply({new: old for old, new in renames.items()})
