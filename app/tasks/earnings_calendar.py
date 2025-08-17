"""
Earnings Calendar Ingestion Task

Fetches upcoming and recent earnings announcements from various sources.
Earnings dates are critical events that often drive significant price movements.
"""

import hashlib
import json
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
        
        # Note: This is a mock implementation. Real implementation would need
        # proper API access or web scraping with appropriate rate limiting
        
        # For now, we'll use Yahoo Finance earnings calendar endpoint
        # In production, consider using Alpha Vantage, IEX Cloud, or Polygon.io
        
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
            status="running",
            started_at=datetime.utcnow(),
            details={
                "task_id": task_id,
                "start_date": start_date,
                "end_date": end_date
            }
        )
        db.add(job_run)
        db.commit()
        
        # Get list of tracked stocks
        stocks = db.query(Stock).all()
        stock_tickers = {stock.symbol: stock for stock in stocks}
        
        earnings_processed = 0
        earnings_new = 0
        earnings_duplicate = 0
        
        # For each stock, check if there's an earnings date in range
        # This is a simplified approach - real implementation would batch query
        for ticker, stock in stock_tickers.items():
            try:
                # Generate mock earnings data for demonstration
                # In production, this would call actual API
                
                # Simulate quarterly earnings (every ~90 days)
                days_since_ipo = (datetime.utcnow() - stock.created_at).days
                quarters_since = days_since_ipo // 90
                next_earnings_days = (quarters_since + 1) * 90 - days_since_ipo
                
                # Check if earnings falls within our window
                if -days_back <= next_earnings_days <= days_ahead:
                    earnings_date = datetime.utcnow() + timedelta(days=next_earnings_days)
                    
                    # Create unique identifier for this earnings event
                    event_id = f"{ticker}_earnings_{earnings_date.strftime('%Y%m%d')}"
                    url = f"https://earnings.example.com/{ticker}/{earnings_date.strftime('%Y-%m-%d')}"
                    url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
                    
                    # Check if already exists
                    existing = db.query(Article).filter(
                        Article.url_hash == url_hash
                    ).first()
                    
                    if existing:
                        earnings_duplicate += 1
                        continue
                    
                    # Determine timing
                    if next_earnings_days < 0:
                        timing = "reported"
                        title = f"{ticker} Reported Q{(quarters_since % 4) + 1} Earnings"
                        content = f"{stock.company_name} reported earnings on {earnings_date.strftime('%B %d, %Y')}."
                    elif next_earnings_days == 0:
                        timing = "today"
                        title = f"{ticker} Reports Earnings Today"
                        content = f"{stock.company_name} is scheduled to report earnings today after market close."
                    else:
                        timing = "upcoming"
                        title = f"{ticker} Earnings Scheduled for {earnings_date.strftime('%B %d')}"
                        content = f"{stock.company_name} will report Q{((quarters_since + 1) % 4) + 1} earnings on {earnings_date.strftime('%B %d, %Y')}."
                    
                    # Create article record for earnings event
                    article = Article(
                        source_id=data_source.id,
                        url=url,
                        url_hash=url_hash,
                        title=title,
                        published_at=datetime.utcnow(),
                        raw_content=content,
                        tickers=[ticker],
                        sentiment=0.5,  # Neutral for earnings announcements
                        language="en",
                        metadata={
                            "event_type": "earnings",
                            "earnings_date": earnings_date.isoformat(),
                            "timing": timing,
                            "quarter": f"Q{((quarters_since + 1) % 4) + 1}",
                            "fiscal_year": earnings_date.year
                        }
                    )
                    
                    db.add(article)
                    earnings_new += 1
                    earnings_processed += 1
                    
            except Exception as e:
                print(f"   ⚠️  Error processing earnings for {ticker}: {e}")
                continue
        
        db.commit()
        
        # Update job run
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = earnings_new
        job_run.details.update({
            "earnings_new": earnings_new,
            "earnings_duplicate": earnings_duplicate,
            "total_processed": earnings_processed
        })
        db.commit()
        
        print(f"✅ Earnings calendar ingestion complete: {earnings_new} new events")
        
        return {
            "status": "success",
            "earnings_new": earnings_new,
            "earnings_duplicate": earnings_duplicate
        }
        
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
                        days_until = (earnings_date - datetime.utcnow()).days
                        
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
                            published_at=datetime.utcnow(),
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
