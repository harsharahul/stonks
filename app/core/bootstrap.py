"""Database bootstrap, run by the container entrypoint before any process starts.

1. Wait for PostgreSQL to accept connections (up to ``DB_WAIT_SECONDS``, default 90).
2. Bring the schema to the current revision:
   - an empty database gets the schema created from the models and is stamped
     at the Alembic head (the earliest migration only alters tables, so a
     fresh install cannot replay history);
   - a database with tables but no Alembic state is stamped at head;
   - anything else runs ``alembic upgrade head``.
3. Seed the starter universe when the stocks table is empty
   (skip with ``STONKS_SKIP_SEED=1``).

Usage: ``python -m app.core.bootstrap``. Exits non-zero when the database
never becomes reachable, so the container fails loudly instead of serving
an empty schema.
"""
import logging
import os
import sys
import time
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from app.core.database import SessionLocal, engine

logger = logging.getLogger("bootstrap")

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def wait_for_db(timeout: float) -> None:
    deadline = time.monotonic() + timeout
    delay = 1.0
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError as exc:
            if time.monotonic() >= deadline:
                raise SystemExit(f"database not reachable after {timeout:.0f}s: {exc}")
            logger.info("waiting for the database (%s)", str(exc).splitlines()[0][:120])
            time.sleep(delay)
            delay = min(delay * 1.5, 5.0)


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    return cfg


def sync_schema() -> str:
    from alembic import command

    from app.models import Base

    tables = set(inspect(engine).get_table_names())
    cfg = _alembic_config()
    if "alembic_version" in tables:
        command.upgrade(cfg, "head")
        return "upgraded"
    if tables:
        command.stamp(cfg, "head")
        return "stamped-existing"
    Base.metadata.create_all(bind=engine)
    command.stamp(cfg, "head")
    return "created"


def seed() -> int:
    from app.core.seed import seed_stocks

    db = SessionLocal()
    try:
        return seed_stocks(db)
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    wait_for_db(float(os.getenv("DB_WAIT_SECONDS", "90")))
    outcome = sync_schema()
    logger.info("schema %s", outcome)
    if os.getenv("STONKS_SKIP_SEED", "").lower() in ("1", "true", "yes"):
        logger.info("seed skipped by STONKS_SKIP_SEED")
        return
    added = seed()
    if added:
        logger.info("starter universe seeded: %d tickers", added)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover: surfaced by the container logs
        logger.error("bootstrap failed: %s", exc)
        sys.exit(1)
