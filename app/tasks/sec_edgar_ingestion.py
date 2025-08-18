"""
SEC EDGAR RSS Feed Ingestion Task

Fetches SEC filings (8-K, 10-K, 10-Q) from EDGAR RSS feeds.
These contain material events, annual reports, and quarterly reports.
"""

import hashlib
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.article import Article
from app.models.data_source import DataSource
from app.models.etl_job_run import ETLJobRun


class SECEdgarIngestionError(Exception):
    """Custom exception for SEC EDGAR ingestion errors"""
    pass


def extract_cik_from_url(url: str) -> Optional[str]:
    """Extract CIK (Central Index Key) from SEC URL"""
    match = re.search(r'/(\d{10})/', url)
    return match.group(1) if match else None


def extract_filing_type(title: str) -> Optional[str]:
    """Extract filing type from title (8-K, 10-K, 10-Q, etc.)"""
    match = re.search(r'\b(8-K|10-K|10-Q|20-F|DEF 14A|S-1|424B\d)\b', title, re.IGNORECASE)
    return match.group(1).upper() if match else None


def clean_sec_text(text: str) -> str:
    """Clean SEC filing text - remove excessive whitespace and legal boilerplate"""
    if not text:
        return ""
    
    # Remove multiple spaces/newlines
    text = re.sub(r'\s+', ' ', text)
    
    # Truncate very long filings to first 10KB for article storage
    if len(text) > 10000:
        text = text[:10000] + "... [truncated]"
    
    return text.strip()


@shared_task(bind=True)
def fetch_sec_edgar_rss(self, filing_types: List[str] = None, days_back: int = 1) -> Dict:
    """
    Fetch SEC EDGAR RSS feeds for specified filing types.
    
    Args:
        filing_types: List of filing types to fetch (e.g., ['8-K', '10-K', '10-Q'])
                     If None, fetches all recent filings
        days_back: Number of days to look back for filings
    
    Returns:
        Dict with ingestion statistics
    """
    db = SessionLocal()
    task_id = self.request.id
    
    # Default to material filings if not specified
    if filing_types is None:
        filing_types = ['8-K', '10-K', '10-Q']
    
    try:
        print(f"📊 Fetching SEC EDGAR filings: {filing_types} (last {days_back} days)")
        
        # SEC RSS feed URL - gets latest filings
        # Note: SEC.gov has rate limiting, so we'll use a mock feed for now
        edgar_rss_url = "https://www.sec.gov/rss/feeds/latest-filings.xml"
        
        # For development/testing, we can use a mock feed if SEC.gov is rate limited
        # edgar_rss_url = "https://mock-sec-feed.example.com/latest-filings.xml"
        
        # Get or create data source
        data_source = db.query(DataSource).filter(
            DataSource.base_url == edgar_rss_url
        ).first()
        
        if not data_source:
            data_source = DataSource(
                name="SEC EDGAR RSS",
                source_type="rss",
                base_url=edgar_rss_url,
                reliability_score=0.95  # Very high - official government source
            )
            db.add(data_source)
            db.flush()
        
        # Create ETL job run
        job_run = ETLJobRun(
            job_name="sec_edgar_rss",
            status="running",
            started_at=datetime.utcnow(),
            details={
                "task_id": task_id,
                "filing_types": filing_types,
                "days_back": days_back
            }
        )
        db.add(job_run)
        db.commit()
        
        # Fetch RSS feed with proper headers for SEC compliance
        headers = {
            'User-Agent': 'Stonks-Analytics/1.0 (Educational Purpose) contact@stonks-analytics.com',
            'From': 'contact@stonks-analytics.com',
            'Accept': 'application/rss+xml, application/xml, text/xml',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # Retry logic for SEC EDGAR
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = requests.get(edgar_rss_url, headers=headers, timeout=30)
                response.raise_for_status()
                break  # Success, exit retry loop
            except requests.RequestException as e:
                if attempt == max_retries - 1:  # Last attempt
                    raise SECEdgarIngestionError(f"Failed to fetch SEC EDGAR feed after {max_retries} attempts: {e}")
                else:
                    print(f"   ⚠️  SEC EDGAR attempt {attempt + 1} failed: {e}, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
        
        feed = feedparser.parse(response.content)
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        filings_processed = 0
        filings_new = 0
        filings_duplicate = 0
        filings_by_type = {}
        
        for entry in feed.entries:
            try:
                # Parse entry details
                title = entry.title
                link = entry.link
                
                # Extract filing type
                filing_type = extract_filing_type(title)
                if filing_types and filing_type not in filing_types:
                    continue  # Skip if not in requested types
                
                # Parse published date
                published_at = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_at = datetime(*entry.published_parsed[:6])
                    
                    # Skip if older than cutoff
                    if published_at < cutoff_date:
                        continue
                
                # Generate URL hash for deduplication
                url_hash = hashlib.sha256(link.encode('utf-8')).hexdigest()
                
                # Check if already exists
                existing_article = db.query(Article).filter(
                    Article.url_hash == url_hash
                ).first()
                
                if existing_article:
                    filings_duplicate += 1
                    continue
                
                # Extract company info from title
                # Format is usually: "Form TYPE - Company Name (CIK)"
                company_match = re.search(r'Form \S+ - (.+?) \(', title)
                company_name = company_match.group(1) if company_match else "Unknown Company"
                
                # Extract CIK for potential ticker mapping
                cik = extract_cik_from_url(link)
                
                # Try to fetch filing summary (first paragraph of filing)
                summary = entry.summary if hasattr(entry, 'summary') else None
                if not summary:
                    summary = f"SEC {filing_type or 'Filing'} for {company_name}"
                
                # Clean and truncate summary
                summary = clean_sec_text(summary)
                
                # For 8-K, try to extract the event type
                event_items = []
                if filing_type == '8-K' and summary:
                    # Look for Item numbers (e.g., "Item 2.02", "Item 5.02")
                    item_matches = re.findall(r'Item \d+\.\d+', summary)
                    event_items = list(set(item_matches))  # Unique items
                
                # Create article record
                article = Article(
                    source_id=data_source.id,
                    url=link,
                    url_hash=url_hash,
                    title=title,
                    published_at=published_at,
                    raw_content=summary,
                    # We'll need a separate task to map CIK to tickers
                    tickers=[],  # Will be populated by entity linking
                    sentiment=0.5,  # Neutral default for filings
                    language="en",
                    metadata={
                        "filing_type": filing_type,
                        "company_name": company_name,
                        "cik": cik,
                        "event_items": event_items if event_items else None
                    }
                )
                
                db.add(article)
                filings_new += 1
                filings_processed += 1
                
                # Track by type
                if filing_type:
                    filings_by_type[filing_type] = filings_by_type.get(filing_type, 0) + 1
                
            except Exception as e:
                print(f"   ⚠️  Error processing SEC filing: {e}")
                db.rollback()
                continue
        
        db.commit()
        
        # Update job run status
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = filings_new
        job_run.details.update({
            "filings_new": filings_new,
            "filings_duplicate": filings_duplicate,
            "filings_by_type": filings_by_type,
            "total_processed": filings_processed
        })
        db.commit()
        
        print(f"✅ SEC EDGAR ingestion complete: {filings_new} new filings")
        print(f"   By type: {filings_by_type}")
        
        return {
            "status": "success",
            "filings_new": filings_new,
            "filings_duplicate": filings_duplicate,
            "filings_by_type": filings_by_type
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
        print(f"❌ Error in SEC EDGAR ingestion: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def map_cik_to_tickers(self, limit: int = 100) -> Dict:
    """
    Map CIK numbers to stock tickers for articles that don't have tickers.
    Uses SEC's company tickers JSON file.
    
    Args:
        limit: Maximum number of articles to process in one run
        
    Returns:
        Dict with mapping statistics
    """
    db = SessionLocal()
    
    try:
        print(f"🔗 Mapping CIK to tickers (limit: {limit})")
        
        # Fetch SEC's company tickers mapping
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        
        try:
            response = requests.get(tickers_url, timeout=30)
            response.raise_for_status()
            cik_ticker_map = {}
            
            # Parse the JSON - it's a dict with numeric keys
            data = response.json()
            for key, company in data.items():
                # Pad CIK with zeros to make it 10 digits
                cik = str(company.get('cik_str', '')).zfill(10)
                ticker = company.get('ticker', '')
                if cik and ticker:
                    cik_ticker_map[cik] = ticker.upper()
                    
        except Exception as e:
            print(f"   ⚠️  Failed to fetch CIK mapping: {e}")
            return {"status": "error", "error": str(e)}
        
        # Find articles with CIK but no tickers
        from sqlalchemy import and_, or_, func
        
        articles = db.query(Article).filter(
            and_(
                func.jsonb_extract_path_text(Article.metadata, 'cik').isnot(None),
                or_(
                    Article.tickers == None,
                    Article.tickers == []
                )
            )
        ).limit(limit).all()
        
        mapped_count = 0
        unmapped_count = 0
        
        for article in articles:
            cik = article.metadata.get('cik')
            if cik and cik in cik_ticker_map:
                ticker = cik_ticker_map[cik]
                article.tickers = [ticker]
                mapped_count += 1
                print(f"   ✓ Mapped CIK {cik} → {ticker}")
            else:
                unmapped_count += 1
        
        db.commit()
        
        print(f"✅ CIK mapping complete: {mapped_count} mapped, {unmapped_count} unmapped")
        
        return {
            "status": "success",
            "mapped_count": mapped_count,
            "unmapped_count": unmapped_count,
            "total_cik_mappings": len(cik_ticker_map)
        }
        
    except Exception as e:
        print(f"❌ Error in CIK mapping: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()
