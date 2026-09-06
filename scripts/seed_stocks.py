#!/usr/bin/env python3
"""Seed the starter universe into an empty stocks table (also done by the container bootstrap)."""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import SessionLocal  # noqa: E402
from app.core.seed import seed_stocks  # noqa: E402

if __name__ == "__main__":
    db = SessionLocal()
    try:
        added = seed_stocks(db)
        print(f"seeded {added} stocks" if added else "stocks table already populated, nothing to do")
    finally:
        db.close()
