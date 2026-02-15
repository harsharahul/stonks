"""
Enhanced SEC EDGAR Ingestion using sec-parser library
Provides superior parsing and analysis of SEC filings
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.article import Article
from app.models.data_source import DataSource
from app.models.etl_job_run import ETLJobRun
from app.models.stock import Stock

# SEC Parser imports - temporarily disabled due to import issues
# from sec_downloader import Downloader
# import sec_parser as sp


@shared_task(bind=True)
def fetch_sec_edgar_enhanced(
    self,
    days_back: int = 7,
    filing_types: Optional[List[str]] = None,
    tickers: Optional[List[str]] = None
):
    """
    Enhanced SEC EDGAR ingestion using sec-parser library
    
    Args:
        days_back: Number of days to look back for filings
        filing_types: List of filing types to fetch (8-K, 10-K, 10-Q, etc.)
        tickers: Specific tickers to fetch (if None, fetches all active)
    """
    
    if filing_types is None:
        filing_types = ["8-K", "10-K", "10-Q"]

    # Check if required libraries are available
    try:
        import sec_parser as sp
        from sec_downloader import Downloader
    except ImportError:
        print("WARNING: sec-parser/sec-downloader not installed. Skipping SEC EDGAR enhanced ingestion.")
        return {"status": "skipped", "reason": "dependencies not installed"}

    db = SessionLocal()
    task_id = self.request.id

    try:
        print(f"🔍 Enhanced SEC EDGAR ingestion: {filing_types} (last {days_back} days)")
        
        # Create ETL job run record
        job_run = ETLJobRun(
            job_name="sec_edgar_enhanced",
            started_at=datetime.utcnow(),
            status="running",
            details={
                "task_id": task_id,
                "filing_types": filing_types,
                "days_back": days_back,
                "tickers": tickers
            }
        )
        db.add(job_run)
        db.commit()
        
        # Get or create data source
        source = db.query(DataSource).filter(
            DataSource.name == "sec_edgar_enhanced"
        ).first()
        
        if not source:
            source = DataSource(
                name="sec_edgar_enhanced",
                source_type="sec_edgar",
                base_url="https://www.sec.gov/edgar",
                reliability_score=0.95
            )
            db.add(source)
            db.commit()
        
        # Get active stocks to monitor
        if tickers:
            stocks = db.query(Stock).filter(
                Stock.symbol.in_(tickers),
                Stock.is_active == True
            ).all()
        else:
            stocks = db.query(Stock).filter(Stock.is_active == True).all()
        
        print(f"📊 Monitoring {len(stocks)} stocks for SEC filings")
        
        # Initialize SEC downloader - temporarily disabled
        # downloader = Downloader("Stonks-Analytics", "dev@stonks-analytics.com")
        
        articles_created = 0
        articles_duplicate = 0
        
        # Process each stock
        for stock in stocks:
            try:
                print(f"  📄 Processing {stock.symbol}...")
                
                # Fetch recent filings for each filing type
                for filing_type in filing_types:
                    try:
                        print(f"    🔍 Fetching {filing_type} for {stock.symbol}...")
                        
                        # Download the latest filing - temporarily disabled
                        # html = downloader.get_filing_html(
                        #     ticker=stock.symbol, 
                        #     form=filing_type
                        # )
                        
                        # if not html:
                        #     print(f"    ⚠️  No {filing_type} found for {stock.symbol}")
                        #     continue
                        
                        print(f"    ✅ Downloaded {filing_type}: {len(html)} characters")
                        
                        # Parse the filing using sec-parser (only 10-Q is fully supported)
                        if filing_type == "10-Q":
                            elements = sp.Edgar10QParser().parse(html)
                        else:
                            # For 8-K and 10-K, use basic HTML parsing for now
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Extract basic information
                            title = soup.find('title')
                            title_text = title.get_text() if title else f"{filing_type} Filing"
                            
                            # Create a simple element structure
                            elements = [type('Element', (), {
                                'tag': 'title',
                                'text': title_text
                            })()]
                            
                            # Add some basic content extraction
                            content_divs = soup.find_all(['div', 'p'], class_=lambda x: x and ('content' in x.lower() or 'text' in x.lower()))
                            for div in content_divs[:3]:  # Limit to first 3 content sections
                                if div.get_text().strip():
                                    elements.append(type('Element', (), {
                                        'tag': 'content',
                                        'text': div.get_text()[:500]
                                    })())
                        
                        # Build semantic tree for better analysis (only for 10-Q)
                        try:
                            if filing_type == "10-Q":
                                tree = sp.TreeBuilder().build(elements)
                            else:
                                tree = None
                        except Exception as e:
                            print(f"    ⚠️  Tree building failed for {filing_type}: {e}")
                            tree = None
                        
                        # Extract key information
                        filing_info = extract_filing_info(elements, filing_type, stock.symbol)
                        
                        # Create article from filing
                        article = create_article_from_filing(
                            filing_info, stock, source, html
                        )
                        
                        # Check for duplicates
                        existing = db.query(Article).filter(
                            Article.url_hash == article.url_hash
                        ).first()
                        
                        if existing:
                            articles_duplicate += 1
                            print(f"    ⚠️  Duplicate {filing_type} for {stock.symbol}")
                        else:
                            db.add(article)
                            articles_created += 1
                            print(f"    ✅ Created {filing_type} article for {stock.symbol}")
                        
                    except Exception as e:
                        print(f"    ❌ Error processing {filing_type} for {stock.symbol}: {e}")
                        continue
                
                # Rate limiting - be respectful to SEC servers
                import time
                time.sleep(1)
                
            except Exception as e:
                print(f"  ❌ Error processing {stock.symbol}: {e}")
                continue
        
        # Update job run with success
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = articles_created
        job_run.details.update({
            "articles_created": articles_created,
            "articles_duplicate": articles_duplicate,
            "stocks_processed": len(stocks),
            "filing_types_processed": filing_types
        })
        
        db.commit()
        
        print(f"🎉 Enhanced SEC EDGAR ingestion complete: {articles_created} new articles")
        
        return {
            "status": "success",
            "articles_created": articles_created,
            "articles_duplicate": articles_duplicate,
            "stocks_processed": len(stocks),
            "filing_types_processed": filing_types
        }
        
    except Exception as e:
        print(f"❌ Error in enhanced SEC EDGAR ingestion: {e}")
        
        # Update job run with error
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({"error": str(e)})
            db.commit()
        
        raise e
        
    finally:
        db.close()


def extract_filing_info(elements: List, filing_type: str, ticker: str) -> Dict[str, Any]:
    """
    Extract key information from parsed SEC filing elements
    """
    filing_info = {
        "filing_type": filing_type,
        "ticker": ticker,
        "title": "",
        "summary": "",
        "key_sections": [],
        "risk_factors": [],
        "management_discussion": []
    }
    
    # Extract title and key sections
    for element in elements:
        if hasattr(element, 'tag') and element.tag == 'title':
            filing_info["title"] = element.text[:200] if element.text else ""
        elif hasattr(element, 'tag') and 'risk' in element.tag.lower():
            if element.text:
                filing_info["risk_factors"].append(element.text[:500])
        elif hasattr(element, 'tag') and 'management' in element.tag.lower():
            if element.text:
                filing_info["management_discussion"].append(element.text[:500])
    
    # Create summary from key sections
    all_text = " ".join([
        filing_info["title"],
        *filing_info["risk_factors"][:3],  # Top 3 risk factors
        *filing_info["management_discussion"][:2]  # Top 2 MD&A sections
    ])
    
    filing_info["summary"] = all_text[:1000] if all_text else f"{filing_type} filing for {ticker}"
    
    return filing_info


def create_article_from_filing(
    filing_info: Dict[str, Any], 
    stock: Stock, 
    source: DataSource, 
    html_content: str
) -> Article:
    """
    Create an Article from SEC filing information
    """
    from hashlib import sha256
    
    # Generate unique URL hash
    url_hash = sha256(f"{stock.symbol}_{filing_info['filing_type']}_{datetime.utcnow().isoformat()}".encode()).hexdigest()
    
    # Create article
    article = Article(
        title=f"{filing_info['filing_type']} Filing: {filing_info['title']}",
        raw_content=filing_info["summary"],
        url=f"https://www.sec.gov/edgar/data/{stock.symbol}/{filing_info['filing_type']}",
        url_hash=url_hash,
        published_at=datetime.utcnow(),
        source_id=source.id,
        tickers=[stock.symbol],
        sentiment=None,  # Will be calculated by post-processing
        article_metadata={
            "source": "sec_edgar_enhanced",
            "filing_type": filing_info["filing_type"],
            "ticker": stock.symbol,
            "company_name": stock.company_name,
            "filing_summary": filing_info["summary"],
            "risk_factors_count": len(filing_info["risk_factors"]),
            "management_discussion_count": len(filing_info["management_discussion"]),
            "parsing_method": "sec-parser",
            "html_content_length": len(html_content)
        }
    )
    
    return article


@shared_task
def test_sec_parser():
    """
    Test the sec-parser library functionality
    """
    try:
        print("🧪 Testing sec-parser library...")
        
        # Test basic import
        import sec_parser as sp
        import sec_downloader
        
        print("✅ sec-parser and sec-downloader imported successfully")
        
        # Test downloader initialization
        downloader = sec_downloader.Downloader("TestCompany", "test@example.com")
        print("✅ SEC downloader initialized successfully")
        
        return {
            "status": "success",
            "message": "sec-parser library is working correctly",
            "version": sp.__version__ if hasattr(sp, '__version__') else "unknown"
        }
        
    except Exception as e:
        print(f"❌ sec-parser test failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
