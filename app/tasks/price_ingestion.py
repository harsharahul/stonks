"""
Price data ingestion tasks using Yahoo Finance and Alpha Vantage
"""

import time
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
from decimal import Decimal
from celery import shared_task
import yfinance as yf
import pandas as pd
import requests

from app.core.database import SessionLocal
from app.models import Stock, Price, ETLJobRun


class PriceIngestionError(Exception):
    """Custom exception for price ingestion errors"""
    pass


@shared_task(bind=True)
def fetch_yahoo_finance_prices(
    self,
    symbol: str,
    period: str = "5d",
    backfill_days: Optional[int] = None
) -> Dict:
    """
    Fetch price data for a single symbol from Yahoo Finance
    
    Args:
        symbol: Stock ticker symbol
        period: Period to fetch (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        backfill_days: Number of days to backfill (overrides period)
        
    Returns:
        Dictionary with ingestion results
    """
    
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        print(f"📈 Fetching Yahoo Finance data for {symbol}")
        
        # Verify stock exists in our database
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            raise PriceIngestionError(f"Stock {symbol} not found in database")
        
        # Create ETL job run
        job_run = ETLJobRun(
            job_name=f"fetch_yahoo_prices_{symbol}",
            status="running",
            details={
                "task_id": task_id,
                "symbol": symbol,
                "period": period,
                "backfill_days": backfill_days
            }
        )
        db.add(job_run)
        db.commit()
        
        # Determine date range
        if backfill_days:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=backfill_days)
            period_str = f"{backfill_days}d"
        else:
            period_str = period
            start_date = None
            end_date = None
        
        # Fetch data from Yahoo Finance
        try:
            ticker = yf.Ticker(symbol)
            
            if start_date and end_date:
                hist = ticker.history(start=start_date, end=end_date)
            else:
                hist = ticker.history(period=period)
            
            if hist.empty:
                raise PriceIngestionError(f"No price data returned for {symbol}")
            
            print(f"✅ Retrieved {len(hist)} price records for {symbol}")
            
        except Exception as e:
            raise PriceIngestionError(f"Yahoo Finance API error for {symbol}: {e}")
        
        # Process and store price data
        prices_new = 0
        prices_updated = 0
        prices_duplicate = 0
        
        for timestamp, row in hist.iterrows():
            try:
                # Convert timestamp to datetime
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
                    existing.open_price = Decimal(str(open_price))
                    existing.high = Decimal(str(high_price))
                    existing.low = Decimal(str(low_price))
                    existing.close = Decimal(str(close_price))
                    existing.volume = volume
                    existing.price = Decimal(str(close_price))
                    prices_updated += 1
                else:
                    # Create new price record
                    price_record = Price(
                        stock_id=stock.id,
                        ts=ts_datetime,
                        symbol=symbol,
                        timestamp=ts_datetime,
                        price=Decimal(str(close_price)),
                        source="yfinance",
                        open_price=Decimal(str(open_price)),
                        high=Decimal(str(high_price)),
                        low=Decimal(str(low_price)),
                        close=Decimal(str(close_price)),
                        volume=volume,
                    )
                    db.add(price_record)
                    prices_new += 1
                
            except Exception as e:
                print(f"   ⚠️  Error processing price record for {ts_datetime}: {e}")
                continue
        
        # Commit all price records
        db.commit()
        
        # Update job run with success
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = prices_new + prices_updated
        job_run.details.update({
            "prices_new": prices_new,
            "prices_updated": prices_updated,
            "prices_duplicate": prices_duplicate,
            "date_range": f"{hist.index.min()} to {hist.index.max()}"
        })
        
        db.commit()
        
        print(f"✅ Yahoo Finance ingestion complete for {symbol}: {prices_new} new, {prices_updated} updated")
        
        return {
            "status": "success",
            "symbol": symbol,
            "prices_new": prices_new,
            "prices_updated": prices_updated,
            "total_processed": prices_new + prices_updated,
            "period": period_str,
            "job_run_id": str(job_run.id)
        }
        
    except Exception as e:
        # Update job run with error
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({
                "error": str(e),
                "error_type": type(e).__name__
            })
            db.commit()
        
        print(f"❌ Error fetching Yahoo Finance data for {symbol}: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def fetch_prices_for_all_stocks(
    self,
    period: str = "5d",
    limit_symbols: Optional[int] = None
) -> Dict:
    """
    Fetch price data for all active stocks
    
    Args:
        period: Period to fetch (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        limit_symbols: Limit to first N symbols (for testing)
        
    Returns:
        Dictionary with overall ingestion results
    """
    
    db = SessionLocal()
    
    try:
        # Get all active stocks
        stocks_query = db.query(Stock).filter(Stock.is_active == True)
        if limit_symbols:
            stocks_query = stocks_query.limit(limit_symbols)
        
        stocks = stocks_query.all()
        symbols = [stock.symbol for stock in stocks]
        
        print(f"🔄 Starting price ingestion for {len(symbols)} stocks (period: {period})")
        
        results = {
            "total_stocks": len(symbols),
            "successful_stocks": 0,
            "failed_stocks": 0,
            "total_prices_new": 0,
            "total_prices_updated": 0,
            "stock_results": []
        }
        
        for i, symbol in enumerate(symbols, 1):
            try:
                print(f"[{i}/{len(symbols)}] Processing {symbol}")
                
                # Add rate limiting to avoid hitting API limits
                if i > 1:
                    time.sleep(1)  # 1 second between requests
                
                result = fetch_yahoo_finance_prices.apply_async(
                    args=[symbol, period]
                ).get()
                
                results["successful_stocks"] += 1
                results["total_prices_new"] += result["prices_new"]
                results["total_prices_updated"] += result["prices_updated"]
                results["stock_results"].append(result)
                
                print(f"   ✅ {symbol}: {result['prices_new']} new, {result['prices_updated']} updated")
                
            except Exception as e:
                print(f"   ❌ {symbol}: {e}")
                results["failed_stocks"] += 1
                results["stock_results"].append({
                    "status": "error",
                    "symbol": symbol,
                    "error": str(e)
                })
        
        success_rate = results["successful_stocks"] / results["total_stocks"] if results["total_stocks"] > 0 else 0
        
        print(f"🎉 Price ingestion complete: {results['total_prices_new']} new, {results['total_prices_updated']} updated from {results['successful_stocks']}/{results['total_stocks']} stocks (success rate: {success_rate:.1%})")
        
        return results
        
    except Exception as e:
        print(f"❌ Error in bulk price ingestion: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def backfill_prices_for_symbol(
    self,
    symbol: str,
    days: int = 30
) -> Dict:
    """
    Backfill historical price data for a specific symbol
    
    Args:
        symbol: Stock ticker symbol
        days: Number of days to backfill
        
    Returns:
        Dictionary with backfill results
    """
    
    print(f"🔄 Backfilling {days} days of price data for {symbol}")
    
    try:
        result = fetch_yahoo_finance_prices.apply_async(
            args=[symbol, None, days]
        ).get()
        
        print(f"✅ Backfill complete for {symbol}: {result['total_processed']} records")
        return result
        
    except Exception as e:
        print(f"❌ Error backfilling {symbol}: {e}")
        raise


def validate_price_data(db, symbol: str, days: int = 5) -> Dict:
    """
    Validate price data quality for a symbol
    
    Args:
        db: Database session
        symbol: Stock ticker symbol  
        days: Number of recent days to validate
        
    Returns:
        Dictionary with validation results
    """
    
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        return {"valid": False, "error": f"Stock {symbol} not found"}
    
    # Get recent price data
    cutoff_date = datetime.now() - timedelta(days=days)
    recent_prices = db.query(Price).filter(
        Price.stock_id == stock.id,
        Price.ts >= cutoff_date
    ).order_by(Price.ts.desc()).all()
    
    if not recent_prices:
        return {"valid": False, "error": f"No recent price data for {symbol}"}
    
    # Validate data quality
    issues = []
    
    for price in recent_prices:
        # Check for valid OHLC relationships
        if price.high < price.low:
            issues.append(f"High < Low on {price.ts}")
        
        if price.open > price.high or price.open < price.low:
            issues.append(f"Open outside High/Low range on {price.ts}")
        
        if price.close > price.high or price.close < price.low:
            issues.append(f"Close outside High/Low range on {price.ts}")
        
        # Check for reasonable values
        if any(p <= 0 for p in [price.open, price.high, price.low, price.close]):
            issues.append(f"Non-positive price on {price.ts}")
        
        if price.volume < 0:
            issues.append(f"Negative volume on {price.ts}")
    
    return {
        "valid": len(issues) == 0,
        "symbol": symbol,
        "records_count": len(recent_prices),
        "date_range": f"{recent_prices[-1].ts} to {recent_prices[0].ts}",
        "issues": issues
    }


@shared_task(bind=True)
def test_price_ingestion(self, test_symbols: List[str] = None) -> Dict:
    """
    Test price ingestion with a limited set of symbols
    
    Args:
        test_symbols: List of symbols to test (defaults to first 3 active stocks)
        
    Returns:
        Dictionary with test results
    """
    
    db = SessionLocal()
    
    try:
        if not test_symbols:
            # Get first 3 active stocks for testing
            stocks = db.query(Stock).filter(Stock.is_active == True).limit(3).all()
            test_symbols = [stock.symbol for stock in stocks]
        
        print(f"🧪 Testing price ingestion with symbols: {test_symbols}")
        
        results = {
            "test_mode": True,
            "symbols_tested": test_symbols,
            "results": [],
            "validation": []
        }
        
        for symbol in test_symbols:
            try:
                # Fetch recent price data
                result = fetch_yahoo_finance_prices.apply_async(
                    args=[symbol, "5d"]
                ).get()
                
                results["results"].append(result)
                
                # Validate the data
                validation = validate_price_data(db, symbol)
                results["validation"].append(validation)
                
                print(f"✅ {symbol}: {result['total_processed']} prices, valid: {validation['valid']}")
                
            except Exception as e:
                print(f"❌ {symbol}: {e}")
                results["results"].append({
                    "status": "error",
                    "symbol": symbol,
                    "error": str(e)
                })
        
        return results
        
    finally:
        db.close()
