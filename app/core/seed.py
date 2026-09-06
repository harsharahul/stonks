"""Starter universe seeded into an empty database.

A handful of widely followed large caps across sectors, enough for the
dashboards to show something on first start. Operators add their own
tickers from the UI; the seed never runs again once the table has rows.
"""
import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.stock import Stock

logger = logging.getLogger(__name__)

SEED_STOCKS = [
    {"symbol": "AAPL", "company_name": "Apple Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    {"symbol": "MSFT", "company_name": "Microsoft Corporation", "sector": "Technology", "exchange": "NASDAQ"},
    {"symbol": "GOOGL", "company_name": "Alphabet Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    {"symbol": "AMZN", "company_name": "Amazon.com Inc.", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    {"symbol": "META", "company_name": "Meta Platforms Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    {"symbol": "TSLA", "company_name": "Tesla Inc.", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    {"symbol": "NVDA", "company_name": "NVIDIA Corporation", "sector": "Technology", "exchange": "NASDAQ"},
    {"symbol": "JPM", "company_name": "JPMorgan Chase & Co.", "sector": "Financial Services", "exchange": "NYSE"},
    {"symbol": "BAC", "company_name": "Bank of America Corporation", "sector": "Financial Services", "exchange": "NYSE"},
    {"symbol": "WFC", "company_name": "Wells Fargo & Company", "sector": "Financial Services", "exchange": "NYSE"},
    {"symbol": "JNJ", "company_name": "Johnson & Johnson", "sector": "Healthcare", "exchange": "NYSE"},
    {"symbol": "PFE", "company_name": "Pfizer Inc.", "sector": "Healthcare", "exchange": "NYSE"},
    {"symbol": "UNH", "company_name": "UnitedHealth Group Inc.", "sector": "Healthcare", "exchange": "NYSE"},
    {"symbol": "KO", "company_name": "The Coca-Cola Company", "sector": "Consumer Staples", "exchange": "NYSE"},
    {"symbol": "PEP", "company_name": "PepsiCo Inc.", "sector": "Consumer Staples", "exchange": "NASDAQ"},
    {"symbol": "XOM", "company_name": "Exxon Mobil Corporation", "sector": "Energy", "exchange": "NYSE"},
    {"symbol": "DIS", "company_name": "The Walt Disney Company", "sector": "Communication Services", "exchange": "NYSE"},
    {"symbol": "HD", "company_name": "The Home Depot Inc.", "sector": "Consumer Discretionary", "exchange": "NYSE"},
    {"symbol": "WMT", "company_name": "Walmart Inc.", "sector": "Consumer Staples", "exchange": "NYSE"},
    {"symbol": "V", "company_name": "Visa Inc.", "sector": "Financial Services", "exchange": "NYSE"},
]


def seed_stocks(db: Session) -> int:
    """Insert the starter universe when the stocks table is empty. Returns rows added."""
    existing = db.query(Stock).count()
    if existing > 0:
        logger.info("stocks table already has %d rows, seed skipped", existing)
        return 0
    for row in SEED_STOCKS:
        db.add(Stock(id=str(uuid4()), is_active=True, **row))
    db.commit()
    logger.info("seeded %d starter stocks", len(SEED_STOCKS))
    return len(SEED_STOCKS)
