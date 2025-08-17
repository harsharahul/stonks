#!/usr/bin/env python3
"""
Test price data ingestion functionality
"""

import sys
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models import Stock, Price
import yfinance as yf
import pandas as pd


def test_yahoo_finance_direct(symbol: str = "AAPL"):
    """Test Yahoo Finance API directly"""
    
    print(f"🧪 Testing Yahoo Finance API directly for {symbol}")
    
    try:
        # Test yfinance directly
        ticker = yf.Ticker(symbol)
        
        # Get 5 days of data
        hist = ticker.history(period="5d")
        
        if hist.empty:
            print(f"❌ No data returned for {symbol}")
            return False
        
        print(f"✅ Retrieved {len(hist)} price records for {symbol}")
        print(f"📊 Date range: {hist.index.min()} to {hist.index.max()}")
        print(f"💰 Latest close: ${hist['Close'].iloc[-1]:.2f}")
        print(f"📈 Price range: ${hist['Low'].min():.2f} - ${hist['High'].max():.2f}")
        print(f"📊 Avg volume: {hist['Volume'].mean():,.0f}")
        
        # Show sample data
        print(f"\n📋 Sample data (last 3 days):")
        for timestamp, row in hist.tail(3).iterrows():
            date_str = timestamp.strftime("%Y-%m-%d")
            print(f"   {date_str}: O=${row['Open']:.2f}, H=${row['High']:.2f}, L=${row['Low']:.2f}, C=${row['Close']:.2f}, V={row['Volume']:,}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Yahoo Finance API: {e}")
        return False


def store_price_data_direct(db, symbol: str, days: int = 5):
    """Store price data directly to database"""
    
    print(f"\n📈 Storing {days} days of price data for {symbol}")
    
    try:
        # Get stock record
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            print(f"❌ Stock {symbol} not found in database")
            return False
        
        print(f"✅ Found stock: {stock.symbol} - {stock.company_name}")
        
        # Fetch data from Yahoo Finance
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{days}d")
        
        if hist.empty:
            print(f"❌ No price data returned for {symbol}")
            return False
        
        print(f"📊 Retrieved {len(hist)} price records from Yahoo Finance")
        
        # Count existing prices
        initial_count = db.query(Price).filter(Price.stock_id == stock.id).count()
        
        # Process and store price data
        prices_new = 0
        prices_updated = 0
        
        for timestamp, row in hist.iterrows():
            try:
                # Convert timestamp
                if hasattr(timestamp, 'to_pydatetime'):
                    ts_datetime = timestamp.to_pydatetime()
                else:
                    ts_datetime = pd.to_datetime(timestamp).to_pydatetime()
                
                # Extract OHLCV data
                open_price = float(row['Open']) if not pd.isna(row['Open']) else None
                high_price = float(row['High']) if not pd.isna(row['High']) else None
                low_price = float(row['Low']) if not pd.isna(row['Low']) else None
                close_price = float(row['Close']) if not pd.isna(row['Close']) else None
                volume = int(row['Volume']) if not pd.isna(row['Volume']) else 0
                
                # Skip if essential data is missing
                if not all([open_price, high_price, low_price, close_price]):
                    print(f"   ⚠️  Skipping {ts_datetime} - missing OHLC data")
                    continue
                
                # Check if price record already exists
                existing = db.query(Price).filter(
                    Price.stock_id == stock.id,
                    Price.ts == ts_datetime
                ).first()
                
                if existing:
                    # Update existing record
                    existing.open = Decimal(str(open_price))
                    existing.high = Decimal(str(high_price))
                    existing.low = Decimal(str(low_price))
                    existing.close = Decimal(str(close_price))
                    existing.volume = volume
                    prices_updated += 1
                    print(f"   🔄 Updated: {ts_datetime.date()} - ${close_price:.2f}")
                else:
                    # Create new price record
                    price_record = Price(
                        stock_id=stock.id,
                        ts=ts_datetime,
                        open=Decimal(str(open_price)),
                        high=Decimal(str(high_price)),
                        low=Decimal(str(low_price)),
                        close=Decimal(str(close_price)),
                        volume=volume
                    )
                    db.add(price_record)
                    prices_new += 1
                    print(f"   ✅ Added: {ts_datetime.date()} - ${close_price:.2f}")
                
            except Exception as e:
                print(f"   ❌ Error processing {ts_datetime}: {e}")
                continue
        
        # Commit changes
        db.commit()
        
        # Final count
        final_count = db.query(Price).filter(Price.stock_id == stock.id).count()
        
        print(f"💾 Price data stored successfully:")
        print(f"   New records: {prices_new}")
        print(f"   Updated records: {prices_updated}")
        print(f"   Total records: {final_count} (+{final_count - initial_count})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error storing price data: {e}")
        db.rollback()
        return False


def validate_stored_prices(db, symbol: str):
    """Validate stored price data"""
    
    print(f"\n🔍 Validating stored price data for {symbol}")
    
    try:
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            print(f"❌ Stock {symbol} not found")
            return False
        
        # Get recent prices
        recent_prices = db.query(Price).filter(
            Price.stock_id == stock.id
        ).order_by(Price.ts.desc()).limit(10).all()
        
        if not recent_prices:
            print(f"❌ No price data found for {symbol}")
            return False
        
        print(f"📊 Found {len(recent_prices)} recent price records")
        
        # Validate data quality
        issues = []
        valid_count = 0
        
        for price in recent_prices:
            record_issues = []
            
            # Check OHLC relationships
            if price.high < price.low:
                record_issues.append("High < Low")
            
            if price.open > price.high or price.open < price.low:
                record_issues.append("Open outside High/Low range")
            
            if price.close > price.high or price.close < price.low:
                record_issues.append("Close outside High/Low range")
            
            # Check for reasonable values
            if any(p <= 0 for p in [price.open, price.high, price.low, price.close]):
                record_issues.append("Non-positive prices")
            
            if price.volume < 0:
                record_issues.append("Negative volume")
            
            if record_issues:
                issues.append(f"{price.ts.date()}: {', '.join(record_issues)}")
            else:
                valid_count += 1
        
        # Show sample data
        print(f"\n📋 Recent price data (last 5 records):")
        for price in recent_prices[:5]:
            date_str = price.ts.strftime("%Y-%m-%d")
            print(f"   {date_str}: O=${price.open}, H=${price.high}, L=${price.low}, C=${price.close}, V={price.volume:,}")
        
        # Validation summary
        if issues:
            print(f"\n⚠️  Data quality issues found:")
            for issue in issues:
                print(f"   • {issue}")
        
        print(f"\n✅ Validation summary:")
        print(f"   Valid records: {valid_count}/{len(recent_prices)}")
        print(f"   Issues found: {len(issues)}")
        print(f"   Data quality: {'Good' if len(issues) == 0 else 'Needs attention'}")
        
        return len(issues) == 0
        
    except Exception as e:
        print(f"❌ Error validating price data: {e}")
        return False


def test_price_ingestion_full():
    """Full price ingestion test"""
    
    db = SessionLocal()
    
    try:
        print("🧪 Testing Price Data Ingestion")
        print("=" * 50)
        
        # Test symbols
        test_symbols = ["AAPL", "MSFT", "GOOGL"]
        
        # Step 1: Test Yahoo Finance API directly
        print("\n1️⃣ Testing Yahoo Finance API...")
        api_results = []
        for symbol in test_symbols:
            result = test_yahoo_finance_direct(symbol)
            api_results.append(result)
            time.sleep(1)  # Rate limiting
        
        successful_api_tests = sum(api_results)
        print(f"\n📊 API Test Results: {successful_api_tests}/{len(test_symbols)} successful")
        
        if successful_api_tests == 0:
            print("❌ No API tests passed, skipping database tests")
            return False
        
        # Step 2: Test storing data to database
        print("\n2️⃣ Testing database storage...")
        storage_results = []
        for symbol in test_symbols[:2]:  # Test first 2 symbols
            result = store_price_data_direct(db, symbol)
            storage_results.append(result)
        
        successful_storage = sum(storage_results)
        print(f"\n📊 Storage Test Results: {successful_storage}/{len(storage_results)} successful")
        
        # Step 3: Validate stored data
        print("\n3️⃣ Validating stored data...")
        validation_results = []
        for symbol in test_symbols[:2]:
            result = validate_stored_prices(db, symbol)
            validation_results.append(result)
        
        successful_validation = sum(validation_results)
        print(f"\n📊 Validation Results: {successful_validation}/{len(validation_results)} passed")
        
        # Overall summary
        print(f"\n🎉 Price Ingestion Test Summary:")
        print(f"   Yahoo Finance API: {successful_api_tests}/{len(test_symbols)} working")
        print(f"   Database storage: {successful_storage}/{len(storage_results)} working")
        print(f"   Data validation: {successful_validation}/{len(validation_results)} passed")
        
        overall_success = (successful_api_tests > 0 and 
                          successful_storage > 0 and 
                          successful_validation > 0)
        
        print(f"   Overall result: {'✅ SUCCESS' if overall_success else '❌ NEEDS ATTENTION'}")
        
        return overall_success
        
    except Exception as e:
        print(f"❌ Error in price ingestion test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    test_price_ingestion_full()
