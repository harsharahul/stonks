#!/usr/bin/env python3
"""
Seed script to populate the stocks table with popular stock symbols
"""

import sys
import os
from uuid import uuid4

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models.stock import Stock

# Popular stocks to seed
SEED_STOCKS = [
    # Tech Giants
    {"symbol": "AAPL", "company_name": "Apple Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    {"symbol": "MSFT", "company_name": "Microsoft Corporation", "sector": "Technology", "exchange": "NASDAQ"},
    {"symbol": "GOOGL", "company_name": "Alphabet Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    {"symbol": "AMZN", "company_name": "Amazon.com Inc.", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    {"symbol": "META", "company_name": "Meta Platforms Inc.", "sector": "Technology", "exchange": "NASDAQ"},
    {"symbol": "TSLA", "company_name": "Tesla Inc.", "sector": "Consumer Discretionary", "exchange": "NASDAQ"},
    {"symbol": "NVDA", "company_name": "NVIDIA Corporation", "sector": "Technology", "exchange": "NASDAQ"},
    
    # Financial
    {"symbol": "JPM", "company_name": "JPMorgan Chase & Co.", "sector": "Financial Services", "exchange": "NYSE"},
    {"symbol": "BAC", "company_name": "Bank of America Corporation", "sector": "Financial Services", "exchange": "NYSE"},
    {"symbol": "WFC", "company_name": "Wells Fargo & Company", "sector": "Financial Services", "exchange": "NYSE"},
    
    # Healthcare
    {"symbol": "JNJ", "company_name": "Johnson & Johnson", "sector": "Healthcare", "exchange": "NYSE"},
    {"symbol": "PFE", "company_name": "Pfizer Inc.", "sector": "Healthcare", "exchange": "NYSE"},
    {"symbol": "UNH", "company_name": "UnitedHealth Group Inc.", "sector": "Healthcare", "exchange": "NYSE"},
    
    # Consumer & Energy
    {"symbol": "KO", "company_name": "The Coca-Cola Company", "sector": "Consumer Staples", "exchange": "NYSE"},
    {"symbol": "PEP", "company_name": "PepsiCo Inc.", "sector": "Consumer Staples", "exchange": "NASDAQ"},
    {"symbol": "XOM", "company_name": "Exxon Mobil Corporation", "sector": "Energy", "exchange": "NYSE"},
    
    # Industrial & Retail
    {"symbol": "DIS", "company_name": "The Walt Disney Company", "sector": "Communication Services", "exchange": "NYSE"},
    {"symbol": "HD", "company_name": "The Home Depot Inc.", "sector": "Consumer Discretionary", "exchange": "NYSE"},
    {"symbol": "WMT", "company_name": "Walmart Inc.", "sector": "Consumer Staples", "exchange": "NYSE"},
    {"symbol": "V", "company_name": "Visa Inc.", "sector": "Financial Services", "exchange": "NYSE"},
]

def seed_stocks():
    """Add seed stock data to the database"""
    db = SessionLocal()
    
    try:
        # Check if stocks already exist
        existing_count = db.query(Stock).count()
        if existing_count > 0:
            print(f"Database already has {existing_count} stocks. Skipping seed.")
            return
        
        print("Seeding stocks table...")
        
        for stock_data in SEED_STOCKS:
            stock = Stock(
                id=str(uuid4()),
                symbol=stock_data["symbol"],
                company_name=stock_data["company_name"],
                sector=stock_data["sector"],
                exchange=stock_data["exchange"],
                is_active=True
            )
            db.add(stock)
            print(f"Added: {stock.symbol} - {stock.company_name}")
        
        db.commit()
        print(f"\n✅ Successfully seeded {len(SEED_STOCKS)} stocks!")
        
        # Verify the seed worked
        total_stocks = db.query(Stock).count()
        print(f"Total stocks in database: {total_stocks}")
        
    except Exception as e:
        print(f"❌ Error seeding stocks: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_stocks()
