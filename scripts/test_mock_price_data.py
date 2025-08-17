#!/usr/bin/env python3
"""
Generate mock price data for testing when Yahoo Finance is not accessible
"""

import sys
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models import Stock, Price


def generate_mock_ohlcv(base_price: float, volatility: float = 0.02) -> dict:
    """Generate realistic OHLCV data"""
    
    # Generate price movement
    change_percent = random.uniform(-volatility, volatility)
    
    # Calculate prices
    open_price = base_price
    close_price = base_price * (1 + change_percent)
    
    # High and low based on intraday volatility
    intraday_range = abs(close_price - open_price) * random.uniform(1.5, 3.0)
    high_price = max(open_price, close_price) + intraday_range * random.uniform(0.3, 0.7)
    low_price = min(open_price, close_price) - intraday_range * random.uniform(0.3, 0.7)
    
    # Ensure high >= low and open/close are within range
    high_price = max(high_price, open_price, close_price)
    low_price = min(low_price, open_price, close_price)
    
    # Generate volume (realistic for large cap stocks)
    base_volume = 50_000_000  # 50M shares base
    volume_multiplier = random.uniform(0.5, 2.0)
    volume = int(base_volume * volume_multiplier)
    
    return {
        "open": round(open_price, 2),
        "high": round(high_price, 2),
        "low": round(low_price, 2),
        "close": round(close_price, 2),
        "volume": volume
    }


def generate_mock_price_series(symbol: str, days: int = 30, start_price: float = 150.0) -> list:
    """Generate a series of mock price data"""
    
    print(f"📊 Generating {days} days of mock price data for {symbol}")
    
    price_data = []
    current_price = start_price
    
    # Set different volatility based on symbol
    volatility_map = {
        "AAPL": 0.015,   # Lower volatility for large cap
        "MSFT": 0.015,
        "GOOGL": 0.020,
        "TSLA": 0.040,   # Higher volatility for TSLA
        "NVDA": 0.030,
        "META": 0.025,
    }
    
    volatility = volatility_map.get(symbol, 0.020)
    
    for i in range(days):
        date = datetime.now() - timedelta(days=days-i-1)
        
        # Weekend skip (simple approximation)
        if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            continue
        
        # Generate OHLCV for this day
        ohlcv = generate_mock_ohlcv(current_price, volatility)
        
        price_data.append({
            "date": date,
            "symbol": symbol,
            **ohlcv
        })
        
        # Update current price for next day
        current_price = ohlcv["close"]
        
        # Add some trending behavior
        if random.random() < 0.7:  # 70% chance to continue trend
            trend_factor = 1.001 if current_price > start_price else 0.999
            current_price *= trend_factor
    
    print(f"✅ Generated {len(price_data)} trading days of data")
    print(f"💰 Price range: ${min(d['low'] for d in price_data):.2f} - ${max(d['high'] for d in price_data):.2f}")
    
    return price_data


def store_mock_price_data(db, symbol: str, days: int = 30):
    """Store mock price data for a symbol"""
    
    print(f"\n📈 Storing mock price data for {symbol}")
    
    try:
        # Get stock record
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            print(f"❌ Stock {symbol} not found in database")
            return False
        
        print(f"✅ Found stock: {stock.symbol} - {stock.company_name}")
        
        # Count existing prices
        initial_count = db.query(Price).filter(Price.stock_id == stock.id).count()
        
        # Generate mock data
        price_data = generate_mock_price_series(symbol, days)
        
        # Store price data
        prices_new = 0
        prices_updated = 0
        
        for data in price_data:
            try:
                # Check if price record already exists
                existing = db.query(Price).filter(
                    Price.stock_id == stock.id,
                    Price.ts == data["date"]
                ).first()
                
                if existing:
                    # Update existing record
                    existing.open = Decimal(str(data["open"]))
                    existing.high = Decimal(str(data["high"]))
                    existing.low = Decimal(str(data["low"]))
                    existing.close = Decimal(str(data["close"]))
                    existing.volume = data["volume"]
                    prices_updated += 1
                    print(f"   🔄 Updated: {data['date'].date()} - ${data['close']:.2f}")
                else:
                    # Create new price record
                    price_record = Price(
                        stock_id=stock.id,
                        ts=data["date"],
                        open=Decimal(str(data["open"])),
                        high=Decimal(str(data["high"])),
                        low=Decimal(str(data["low"])),
                        close=Decimal(str(data["close"])),
                        volume=data["volume"]
                    )
                    db.add(price_record)
                    prices_new += 1
                    print(f"   ✅ Added: {data['date'].date()} - ${data['close']:.2f}")
                
            except Exception as e:
                print(f"   ❌ Error processing {data['date']}: {e}")
                continue
        
        # Commit changes
        db.commit()
        
        # Final count
        final_count = db.query(Price).filter(Price.stock_id == stock.id).count()
        
        print(f"💾 Mock price data stored successfully:")
        print(f"   New records: {prices_new}")
        print(f"   Updated records: {prices_updated}")
        print(f"   Total records: {final_count} (+{final_count - initial_count})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error storing mock price data: {e}")
        db.rollback()
        return False


def test_mock_price_ingestion():
    """Test mock price data generation and storage"""
    
    db = SessionLocal()
    
    try:
        print("🧪 Testing Mock Price Data Generation")
        print("=" * 50)
        
        # Test symbols (use our seeded stocks)
        test_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
        
        print(f"📊 Testing with symbols: {test_symbols}")
        
        # Generate and store mock data for each symbol
        results = []
        for i, symbol in enumerate(test_symbols, 1):
            print(f"\n[{i}/{len(test_symbols)}] Processing {symbol}")
            result = store_mock_price_data(db, symbol, days=30)
            results.append(result)
        
        successful_count = sum(results)
        
        # Summary
        print(f"\n🎉 Mock Price Data Test Summary:")
        print(f"   Successful: {successful_count}/{len(test_symbols)}")
        print(f"   Success rate: {successful_count/len(test_symbols)*100:.1f}%")
        
        # Show overall statistics
        total_prices = db.query(Price).count()
        print(f"   Total price records in database: {total_prices}")
        
        # Show sample from each symbol
        print(f"\n📊 Sample data from each symbol:")
        for symbol in test_symbols:
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            if stock:
                latest_price = db.query(Price).filter(
                    Price.stock_id == stock.id
                ).order_by(Price.ts.desc()).first()
                
                if latest_price:
                    print(f"   {symbol}: Latest price ${latest_price.close} on {latest_price.ts.date()}")
        
        # Test price data availability for feature calculations
        print(f"\n🔧 Testing feature calculation readiness:")
        for symbol in test_symbols[:3]:  # Test first 3
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            if stock:
                price_count = db.query(Price).filter(Price.stock_id == stock.id).count()
                recent_prices = db.query(Price).filter(
                    Price.stock_id == stock.id
                ).order_by(Price.ts.desc()).limit(5).all()
                
                if recent_prices:
                    returns_5d = ((recent_prices[0].close - recent_prices[4].close) / recent_prices[4].close) * 100
                    print(f"   {symbol}: {price_count} records, 5-day return: {returns_5d:+.2f}%")
        
        return successful_count > 0
        
    except Exception as e:
        print(f"❌ Error in mock price ingestion test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    test_mock_price_ingestion()
