"""
Earnings Calendar Ingestion Task

Fetches upcoming and recent earnings announcements from various sources.
Earnings dates are critical events that often drive significant price movements.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.article import Article
from app.models.data_source import DataSource
from app.models.etl_job_run import ETLJobRun
from app.models.stock import Stock


class EarningsCalendarError(Exception):
    """Custom exception for earnings calendar ingestion"""
    pass


def parse_earnings_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats from earnings APIs"""
    if not date_str:
        return None
    
    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%m/%d/%Y",
        "%d-%b-%Y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


@shared_task(bind=True)
def fetch_nasdaq_earnings_calendar(self, days_ahead: int = 7, days_back: int = 3) -> Dict:
    """
    Fetch earnings calendar from Nasdaq (via web scraping API).
    
    Args:
        days_ahead: Number of days to look ahead for upcoming earnings
        days_back: Number of days to look back for recent earnings
        
    Returns:
        Dict with ingestion statistics
    """
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        print(f"📅 Fetching Nasdaq earnings calendar (-{days_back} to +{days_ahead} days)")
        
        # Try multiple earnings data sources with fallback
        # Primary: Alpha Vantage (free tier available)
        # Fallback: Mock data for development
        # Future: IEX Cloud, Polygon.io for production
        
        start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end_date = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
        # Get or create data source
        source_name = "Earnings Calendar"
        data_source = db.query(DataSource).filter(
            DataSource.name == source_name
        ).first()
        
        if not data_source:
            data_source = DataSource(
                name=source_name,
                source_type="api",
                base_url="earnings_calendar",
                reliability_score=0.85
            )
            db.add(data_source)
            db.flush()
        
        # Create ETL job run
        job_run = ETLJobRun(
            job_name="earnings_calendar",
            started_at=datetime.utcnow(),
            status="running",
            details={
                "task_id": task_id,
                "start_date": start_date,
                "end_date": end_date
            }
        )
        db.add(job_run)
        db.commit()
        
        # Try Alpha Vantage earnings calendar first
        alpha_vantage_key = os.getenv('ALPHA_VANTAGE_API_KEY')
        if alpha_vantage_key:
            try:
                earnings_data = fetch_alpha_vantage_earnings(alpha_vantage_key, start_date, end_date)
                if earnings_data:
                    print(f"   ✅ Alpha Vantage earnings data: {len(earnings_data)} companies")
                    return process_earnings_data(earnings_data, db, data_source, job_run)
            except Exception as e:
                print(f"   ⚠️  Alpha Vantage failed: {e}, falling back to mock data")
        
        # Fallback to mock data for development
        print("   📝 Using mock earnings data (development mode)")
        mock_earnings = generate_mock_earnings_data(days_ahead, days_back)
        return process_earnings_data(mock_earnings, db, data_source, job_run)
        
    except Exception as e:
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({
                "error": str(e),
                "error_type": type(e).__name__
            })
            db.commit()
        print(f"❌ Error fetching earnings calendar: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def fetch_yahoo_earnings_calendar(self, ticker: str) -> Dict:
    """
    Fetch earnings dates for a specific ticker from Yahoo Finance.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dict with earnings information
    """
    db = SessionLocal()
    
    try:
        print(f"📊 Fetching Yahoo earnings for {ticker}")
        
        # Yahoo Finance earnings endpoint (unofficial)
        # In production, use official API or yfinance library
        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}"
        params = {
            "modules": "calendarEvents,earnings,earningsHistory,earningsTrend"
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Stonks/1.0)'
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            result = data.get('quoteSummary', {}).get('result', [])
            if not result:
                return {"status": "error", "error": "No data found"}
            
            quote_data = result[0]
            calendar_events = quote_data.get('calendarEvents', {})
            
            # Extract earnings date
            earnings_date_raw = calendar_events.get('earnings', {}).get('earningsDate', [])
            if earnings_date_raw:
                # Convert Unix timestamp to datetime
                earnings_timestamp = earnings_date_raw[0].get('raw')
                if earnings_timestamp:
                    earnings_date = datetime.fromtimestamp(earnings_timestamp)
                    
                    # Create or update earnings event article
                    source_name = "Yahoo Finance Earnings"
                    data_source = db.query(DataSource).filter(
                        DataSource.name == source_name
                    ).first()
                    
                    if not data_source:
                        data_source = DataSource(
                            name=source_name,
                            source_type="api",
                            base_url="https://finance.yahoo.com",
                            reliability_score=0.9
                        )
                        db.add(data_source)
                        db.flush()
                    
                    # Create unique URL for this earnings event
                    event_url = f"https://finance.yahoo.com/calendar/earnings?symbol={ticker}&date={earnings_date.strftime('%Y-%m-%d')}"
                    url_hash = hashlib.sha256(event_url.encode('utf-8')).hexdigest()
                    
                    # Check if exists
                    existing = db.query(Article).filter(
                        Article.url_hash == url_hash
                    ).first()
                    
                    if not existing:
                        # Ensure both datetimes are timezone-naive for comparison
                        now = datetime.utcnow()
                        if earnings_date.tzinfo is not None:
                            earnings_date = earnings_date.replace(tzinfo=None)
                        
                        days_until = (earnings_date - now).days
                        
                        if days_until < 0:
                            title = f"{ticker} Reported Earnings on {earnings_date.strftime('%B %d')}"
                        elif days_until == 0:
                            title = f"{ticker} Reports Earnings Today"
                        else:
                            title = f"{ticker} Earnings in {days_until} Days ({earnings_date.strftime('%B %d')})"
                        
                        article = Article(
                            source_id=data_source.id,
                            url=event_url,
                            url_hash=url_hash,
                            title=title,
                            published_at=now,
                            raw_content=f"Earnings date for {ticker}: {earnings_date.strftime('%B %d, %Y')}",
                            tickers=[ticker],
                            sentiment=0.5,
                            language="en",
                            metadata={
                                "event_type": "earnings",
                                "earnings_date": earnings_date.isoformat(),
                                "days_until": days_until,
                                "source": "yahoo_finance"
                            }
                        )
                        
                        db.add(article)
                        db.commit()
                        
                        print(f"✅ Added earnings event for {ticker} on {earnings_date.strftime('%Y-%m-%d')}")
                        
                        return {
                            "status": "success",
                            "ticker": ticker,
                            "earnings_date": earnings_date.isoformat(),
                            "days_until": days_until
                        }
                    else:
                        return {
                            "status": "duplicate",
                            "ticker": ticker,
                            "message": "Earnings event already exists"
                        }
            
            return {
                "status": "no_data",
                "ticker": ticker,
                "message": "No earnings date found"
            }
            
        except requests.RequestException as e:
            return {
                "status": "error",
                "ticker": ticker,
                "error": str(e)
            }
            
    except Exception as e:
        print(f"❌ Error fetching Yahoo earnings for {ticker}: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()


def fetch_alpha_vantage_earnings(api_key: str, start_date: str, end_date: str) -> List[Dict]:
    """
    Fetch earnings calendar from Alpha Vantage API
    
    Args:
        api_key: Alpha Vantage API key
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        List of earnings data dictionaries
    """
    try:
        # Alpha Vantage earnings calendar endpoint
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'EARNINGS_CALENDAR',
            'horizon': '3month',  # 3 month horizon
            'apikey': api_key
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        # Parse CSV response
        if response.text.strip():
            lines = response.text.strip().split('\n')
            if len(lines) > 1:  # Has header + data
                headers = lines[0].split(',')
                earnings_data = []
                
                for line in lines[1:]:  # Skip header
                    values = line.split(',')
                    if len(values) >= len(headers):
                        earnings_entry = dict(zip(headers, values))
                        earnings_data.append(earnings_entry)
                
                print(f"   📊 Alpha Vantage: {len(earnings_data)} earnings entries")
                return earnings_data
        
        return []
        
    except Exception as e:
        print(f"   ❌ Alpha Vantage API error: {e}")
        return []


def generate_mock_earnings_data(days_ahead: int, days_back: int) -> List[Dict]:
    """
    Generate mock earnings data for development/testing
    
    Args:
        days_ahead: Days to look ahead
        days_back: Days to look back
        
    Returns:
        List of mock earnings data
    """
    from app.models.stock import Stock
    
    mock_data = []
    db = SessionLocal()
    
    try:
        # Get some active stocks
        stocks = db.query(Stock).filter(Stock.is_active == True).limit(10).all()
        
        for stock in stocks:
            # Generate random earnings dates within range
            import random
            days_offset = random.randint(-days_back, days_ahead)
            earnings_date = datetime.utcnow() + timedelta(days=days_offset)
            
            mock_data.append({
                'symbol': stock.symbol,
                'company': stock.company_name,
                'earnings_date': earnings_date.strftime('%Y-%m-%d'),
                'estimate': round(random.uniform(0.5, 5.0), 2),
                'actual': None,  # Will be filled after earnings
                'source': 'mock_data'
            })
        
        print(f"   📝 Generated {len(mock_data)} mock earnings entries")
        return mock_data
        
    except Exception as e:
        print(f"   ❌ Error generating mock data: {e}")
        return []
    finally:
        db.close()


def process_earnings_data(earnings_data: List[Dict], db: Session, data_source: DataSource, job_run: ETLJobRun) -> Dict:
    """
    Process and store earnings data
    
    Args:
        earnings_data: List of earnings data dictionaries
        db: Database session
        data_source: Data source record
        job_run: ETL job run record
        
    Returns:
        Processing results
    """
    try:
        processed_count = 0
        new_count = 0
        
        for earnings in earnings_data:
            symbol = earnings.get('symbol', '').upper()
            if not symbol:
                continue
                
            # Check if stock exists
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            if not stock:
                continue  # Skip unknown stocks
            
            # Create earnings event article
            earnings_date = parse_earnings_date(earnings.get('earnings_date', ''))
            if not earnings_date:
                continue
            
            event_url = f"earnings://{symbol}/{earnings_date.strftime('%Y-%m-%d')}"
            url_hash = hashlib.sha256(event_url.encode('utf-8')).hexdigest()
            
            # Check if exists
            existing = db.query(Article).filter(Article.url_hash == url_hash).first()
            if existing:
                processed_count += 1
                continue
            
            # Create new earnings article
            # Ensure both datetimes are timezone-naive for comparison
            now = datetime.utcnow()
            if earnings_date.tzinfo is not None:
                earnings_date = earnings_date.replace(tzinfo=None)
            
            days_until = (earnings_date - now).days
            
            if days_until < 0:
                title = f"{symbol} Reported Earnings on {earnings_date.strftime('%B %d')}"
            elif days_until == 0:
                title = f"{symbol} Reports Earnings Today"
            else:
                title = f"{symbol} Earnings in {days_until} Days ({earnings_date.strftime('%B %d')})"
            
            article = Article(
                source_id=data_source.id,
                url=event_url,
                url_hash=url_hash,
                title=title,
                published_at=now,
                raw_content=f"Earnings date for {symbol}: {earnings_date.strftime('%B %d, %Y')}",
                tickers=[symbol],
                sentiment=0.5,
                language="en",
                metadata={
                    "event_type": "earnings",
                    "earnings_date": earnings_date.isoformat(),
                    "days_until": days_until,
                    "source": earnings.get('source', 'alpha_vantage'),
                    "estimate": earnings.get('estimate'),
                    "actual": earnings.get('actual')
                }
            )
            
            db.add(article)
            new_count += 1
            processed_count += 1
        
        # Update job run
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = processed_count
        job_run.details.update({
            "new_earnings_events": new_count,
            "total_processed": processed_count
        })
        
        db.commit()
        
        return {
            "status": "success",
            "processed": processed_count,
            "new_events": new_count,
            "source": "earnings_calendar"
        }
        
    except Exception as e:
        db.rollback()
        job_run.status = "failed"
        job_run.finished_at = datetime.utcnow()
        job_run.details.update({"error": str(e)})
        db.commit()
        raise EarningsCalendarError(f"Failed to process earnings data: {e}")
