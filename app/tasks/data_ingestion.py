"""
Celery tasks for data ingestion - RSS feeds, news, and price data
"""

import hashlib
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from celery import shared_task
import feedparser
import requests
from bs4 import BeautifulSoup

from app.core.database import SessionLocal
from app.models import Article, DataSource, Stock, ETLJobRun
from app.models.doc_entity import DocEntity


# Financial news RSS feeds configuration
RSS_SOURCES = [
    {
        "name": "Yahoo Finance - Business",
        "url": "https://finance.yahoo.com/news/rssindex",
        "source_type": "rss",
        "reliability_score": 0.85
    },
    {
        "name": "MarketWatch - Top Stories", 
        "url": "http://feeds.marketwatch.com/marketwatch/topstories/",
        "source_type": "rss",
        "reliability_score": 0.80
    },
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "source_type": "rss", 
        "reliability_score": 0.90
    },
    {
        "name": "CNBC Top News",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "source_type": "rss",
        "reliability_score": 0.85
    }
]

GOOGLE_NEWS_URL_TEMPLATE = (
    "https://news.google.com/rss/search?q={query}+when%3A{days}d&hl=en-US&gl=US&ceid=US:en"
)


class NewsIngestionError(Exception):
    """Custom exception for news ingestion errors"""
    pass


def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    text = ' '.join(text.split())
    
    # Remove common HTML entities that might have been missed
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    
    return text.strip()


def extract_text_from_html(html_content: str) -> str:
    """Extract clean text from HTML content"""
    if not html_content:
        return ""
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        return clean_text(text)
        
    except Exception as e:
        print(f"Warning: Error extracting text from HTML: {e}")
        return clean_text(html_content)


def generate_url_hash(url: str) -> str:
    """Generate SHA256 hash for URL deduplication"""
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def extract_tickers_basic(text: str) -> List[str]:
    """Basic ticker extraction using regex patterns"""
    if not text:
        return []
    
    tickers = set()
    
    # Pattern 1: $TICKER format (e.g., $AAPL, $MSFT)
    cashtag_pattern = r'\$([A-Z]{1,5})\b'
    cashtags = re.findall(cashtag_pattern, text.upper())
    tickers.update(cashtags)
    
    # Pattern 2: Exchange notation (e.g., AAPL.O, MSFT.NASDAQ)
    exchange_pattern = r'\b([A-Z]{1,5})\.[A-Z]+\b'
    exchange_tickers = re.findall(exchange_pattern, text.upper())
    tickers.update(exchange_tickers)
    
    # Pattern 3: Standalone tickers in parentheses (e.g., "Apple (AAPL)")
    paren_pattern = r'\(([A-Z]{1,5})\)'
    paren_tickers = re.findall(paren_pattern, text.upper())
    tickers.update(paren_tickers)
    
    # Filter out common false positives
    false_positives = {
        'US', 'USA', 'UK', 'EU', 'NYSE', 'NASDAQ', 'SEC', 'FDA', 'CEO', 'CFO', 'CTO',
        'IPO', 'ETF', 'ESG', 'AI', 'API', 'GDP', 'CPI', 'Q1', 'Q2', 'Q3', 'Q4'
    }
    
    valid_tickers = [t for t in tickers if t not in false_positives and len(t) >= 2]
    
    return list(valid_tickers)[:5]  # Limit to top 5 tickers


def _persist_article(
    db,
    source_name: str,
    source_url: str,
    item_title: str,
    item_link: str,
    item_published: Optional[str],
    raw_content: Optional[str],
    tickers: List[str],
) -> Tuple[bool, Optional[str]]:
    """Persist one article if new. Returns (is_new, article_id)."""
    print(f"🔍 DEBUG: _persist_article called with source_name: {source_name}")
    
    # Compute URL hash for idempotency
    url_hash = hashlib.sha256(item_link.encode("utf-8")).hexdigest()

    existing = db.query(Article).filter(Article.url_hash == url_hash).first()
    if existing:
        print(f"🔍 DEBUG: Article already exists with hash: {url_hash}")
        return False, str(existing.id)

    # Ensure data source exists
    data_source = db.query(DataSource).filter(DataSource.base_url == source_url).first()
    if not data_source:
        data_source = DataSource(
            name=source_name,
            source_type="rss",
            base_url=source_url,
            reliability_score=0.75,
        )
        db.add(data_source)
        db.flush()
        print(f"🔍 DEBUG: Created new data source: {data_source.id}")

    # Parse published date
    published_at = None
    if item_published:
        try:
            published_at = datetime(*feedparser.parse(item_published).updated_parsed[:6])
        except Exception:
            try:
                published_at = datetime.strptime(item_published, "%a, %d %b %Y %H:%M:%S %Z")
            except Exception:
                published_at = None

    # Determine source identifier for metadata
    source_identifier = None
    if "google" in source_name.lower():
        source_identifier = "google_news"
    elif "rss" in source_name.lower():
        source_identifier = "rss_feed"
    else:
        source_identifier = source_name.lower().replace(" ", "_")
    
    print(f"🔍 DEBUG: Setting source_identifier: {source_identifier}")

    article = Article(
        source_id=str(data_source.id),
        url=item_link,
        url_hash=url_hash,
        title=item_title[:500] if item_title else None,
        published_at=published_at,
        raw_content=raw_content,
        tickers=tickers,
        sentiment=None,
        entities=None,
        article_metadata={
            "source": source_identifier,
            "source_name": source_name,
            "ingested_at": datetime.utcnow().isoformat()
        }
    )
    print(f"🔍 DEBUG: Created article with metadata: {article.article_metadata}")
    
    db.add(article)
    db.flush()
    print(f"🔍 DEBUG: Article saved with ID: {article.id}")
    
    return True, str(article.id)


@shared_task(bind=True)
def fetch_google_news_by_ticker(self, ticker: str, days: int = 7) -> Dict:
    """Fetch Google News RSS for a given ticker and persist as articles.

    This is a Celery task for API-triggered ingestion.
    """
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        source_name = "Google News RSS"
        query = ticker
        rss_url = GOOGLE_NEWS_URL_TEMPLATE.format(query=query, days=days)

        # Create ETL job run
        job_run = ETLJobRun(
            job_name=f"google_news_{ticker}",
            started_at=datetime.utcnow(),
            status="running",
            details={"ticker": ticker, "rss_url": rss_url, "task_id": task_id},
        )
        db.add(job_run)
        db.commit()

        headers = {"User-Agent": "Mozilla/5.0 (compatible; Stonks-Analytics/1.0)"}
        resp = requests.get(rss_url, headers=headers, timeout=30)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        new_count = 0
        dup_count = 0
        items = feed.entries[:25]

        for entry in items:
            title = clean_text(entry.get("title", ""))
            link = entry.get("link")
            summary = entry.get("summary", None)
            published = entry.get("published") or entry.get("updated")

            if not link:
                continue

            is_new, _ = _persist_article(
                db=db,
                source_name=source_name,
                source_url=rss_url,
                item_title=title,
                item_link=link,
                item_published=published,
                raw_content=summary,
                tickers=[ticker],
            )
            if is_new:
                new_count += 1
            else:
                dup_count += 1

        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = new_count + dup_count
        job_run.details.update({"articles_new": new_count, "articles_duplicate": dup_count})
        db.commit()

        return {
            "status": "success",
            "ticker": ticker,
            "articles_new": new_count,
            "articles_duplicate": dup_count,
        }
    except Exception as e:
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({"error": str(e)})
            db.commit()
        raise
    finally:
        db.close()


def _fetch_rss_feed_impl(source_config: Dict) -> Dict:
    """
    Core RSS fetch logic for a single source. Used by both the Celery task
    (fetch_rss_feed) and parent tasks that iterate over sources,
    avoiding .apply_async().get() deadlocks.
    """
    db = SessionLocal()

    try:
        source_name = source_config["name"]
        source_url = source_config["url"]

        print(f"📰 Fetching RSS feed: {source_name}")

        # Get or create data source record
        data_source = db.query(DataSource).filter(
            DataSource.base_url == source_url
        ).first()

        if not data_source:
            data_source = DataSource(
                name=source_name,
                source_type=source_config["source_type"],
                base_url=source_url,
                reliability_score=source_config["reliability_score"]
            )
            db.add(data_source)
            db.flush()

        # Fetch RSS feed with timeout and user agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Stonks-Analytics/1.0)'
        }

        try:
            response = requests.get(source_url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise NewsIngestionError(f"Failed to fetch RSS feed: {e}")

        # Parse RSS feed
        feed = feedparser.parse(response.content)

        if feed.bozo:
            print(f"Warning: RSS feed parsing warning for {source_name}: {feed.bozo_exception}")

        # Process articles
        articles_processed = 0
        articles_new = 0
        articles_duplicate = 0

        for entry in feed.entries:
            try:
                title = clean_text(entry.get('title', ''))
                url = entry.get('link', '')

                if not url or not title:
                    continue

                url_hash = generate_url_hash(url)

                existing = db.query(Article).filter(Article.url_hash == url_hash).first()
                if existing:
                    articles_duplicate += 1
                    continue

                published_at = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_at = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published_at = datetime(*entry.updated_parsed[:6])

                content = ""
                if hasattr(entry, 'content') and entry.content:
                    content = entry.content[0].value if entry.content else ""
                elif hasattr(entry, 'summary'):
                    content = entry.summary
                elif hasattr(entry, 'description'):
                    content = entry.description

                raw_content = extract_text_from_html(content)

                full_text = f"{title} {raw_content}"
                tickers = extract_tickers_basic(full_text)

                article = Article(
                    source_id=data_source.id,
                    url=url,
                    url_hash=url_hash,
                    title=title,
                    published_at=published_at,
                    raw_content=raw_content,
                    tickers=tickers if tickers else None,
                    language="en"
                )

                db.add(article)
                db.flush()

                for ticker in tickers:
                    stock_exists = db.query(Stock).filter(Stock.symbol == ticker).first()
                    if stock_exists:
                        entity = DocEntity(
                            doc_id=article.id,
                            ticker=ticker,
                            company_name=stock_exists.company_name,
                            confidence=0.8,
                            method="rss_regex"
                        )
                        db.add(entity)

                articles_new += 1
                articles_processed += 1

            except Exception as e:
                print(f"Warning: Error processing article from {source_name}: {e}")
                continue

        db.commit()

        print(f"✅ RSS ingestion complete for {source_name}: {articles_new} new, {articles_duplicate} duplicates")

        return {
            "status": "success",
            "source_name": source_name,
            "articles_new": articles_new,
            "articles_duplicate": articles_duplicate,
            "articles_processed": articles_processed,
            "feed_title": feed.feed.get('title', ''),
            "feed_entries_total": len(feed.entries),
        }

    except Exception as e:
        print(f"❌ Error fetching RSS feed {source_config.get('name', 'unknown')}: {e}")
        raise

    finally:
        db.close()


@shared_task(bind=True)
def fetch_rss_feed(self, source_config: Dict) -> Dict:
    """
    Fetch and parse a single RSS feed (Celery task wrapper).
    """
    db = SessionLocal()
    task_id = self.request.id

    try:
        source_name = source_config["name"]

        # Create ETL job run
        job_run = ETLJobRun(
            job_name=f"fetch_rss_feed_{source_name}",
            started_at=datetime.utcnow(),
            status="running",
            details={
                "task_id": task_id,
                "source_name": source_name,
                "source_url": source_config["url"]
            }
        )
        db.add(job_run)
        db.commit()

        result = _fetch_rss_feed_impl(source_config)

        # Update job run with success
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = result["articles_processed"]
        job_run.details.update({
            "articles_new": result["articles_new"],
            "articles_duplicate": result["articles_duplicate"],
            "feed_title": result.get("feed_title", ""),
            "feed_entries_total": result.get("feed_entries_total", 0),
        })
        db.commit()

        result["job_run_id"] = str(job_run.id)
        return result

    except Exception as e:
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({
                "error": str(e),
                "error_type": type(e).__name__
            })
            db.commit()
        raise

    finally:
        db.close()


@shared_task(bind=True)
def fetch_all_rss_feeds(self) -> Dict:
    """
    Fetch all configured RSS feeds
    
    Returns:
        Dictionary with overall ingestion results
    """
    
    print(f"🔄 Starting RSS feed ingestion for {len(RSS_SOURCES)} sources")
    
    results = {
        "total_sources": len(RSS_SOURCES),
        "successful_sources": 0,
        "failed_sources": 0,
        "total_articles_new": 0,
        "total_articles_duplicate": 0,
        "source_results": []
    }
    
    for source_config in RSS_SOURCES:
        try:
            # Add rate limiting between sources
            time.sleep(1)

            # Direct call instead of .apply_async().get() to avoid deadlock
            result = _fetch_rss_feed_impl(source_config)

            results["successful_sources"] += 1
            results["total_articles_new"] += result["articles_new"]
            results["total_articles_duplicate"] += result["articles_duplicate"]
            results["source_results"].append(result)

        except Exception as e:
            print(f"❌ Failed to fetch RSS source {source_config['name']}: {e}")
            results["failed_sources"] += 1
            results["source_results"].append({
                "status": "error",
                "source_name": source_config["name"],
                "error": str(e)
            })
    
    success_rate = results["successful_sources"] / results["total_sources"]
    
    print(f"🎉 RSS ingestion complete: {results['total_articles_new']} new articles from {results['successful_sources']}/{results['total_sources']} sources (success rate: {success_rate:.1%})")
    
    return results


@shared_task(bind=True)
def test_rss_ingestion(self, limit_sources: int = 2) -> Dict:
    """
    Test RSS ingestion with a limited number of sources
    
    Args:
        limit_sources: Number of sources to test (default 2)
        
    Returns:
        Dictionary with test results
    """
    
    test_sources = RSS_SOURCES[:limit_sources]
    
    print(f"🧪 Testing RSS ingestion with {len(test_sources)} sources")
    
    results = {
        "test_mode": True,
        "sources_tested": len(test_sources),
        "results": []
    }
    
    for source_config in test_sources:
        try:
            # Direct call instead of .apply_async().get()
            result = _fetch_rss_feed_impl(source_config)
            results["results"].append(result)

        except Exception as e:
            print(f"❌ Test failed for {source_config['name']}: {e}")
            results["results"].append({
                "status": "error",
                "source_name": source_config["name"],
                "error": str(e)
            })
    
    return results


@shared_task(bind=True)
def ingest_rss_feeds_task(self, tickers: Optional[List[str]] = None) -> Dict:
    """
    Automated RSS ingestion task for all configured sources
    
    Args:
        tickers: Specific tickers to fetch news for (defaults to all active)
        
    Returns:
        Dict with ingestion statistics
    """
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        print(f"📰 Starting automated RSS ingestion task {task_id}")
        
        # Get or create data source
        source_name = "Automated RSS Ingestion"
        data_source = db.query(DataSource).filter(
            DataSource.name == source_name
        ).first()
        
        if not data_source:
            data_source = DataSource(
                name=source_name,
                source_type="automated",
                base_url="rss_automation",
                reliability_score=0.9
            )
            db.add(data_source)
            db.flush()
        
        # Create ETL job run
        job_run = ETLJobRun(
            job_name="news_ingestion",
            started_at=datetime.utcnow(),
            status="running",
            details={
                "task_id": task_id,
                "tickers_requested": tickers,
                "sources_processed": []
            }
        )
        db.add(job_run)
        db.commit()
        
        # Get tickers to process
        if tickers is None:
            # Get all active tickers from stocks table
            from app.models.stock import Stock
            stocks = db.query(Stock).filter(Stock.is_active == True).all()
            tickers = [stock.symbol for stock in stocks]
        
        print(f"   📊 Processing {len(tickers)} tickers")
        
        total_articles = 0
        total_new = 0
        total_duplicate = 0
        sources_processed = []
        
        # Process each ticker
        for ticker in tickers[:20]:  # Limit to 20 for performance
            try:
                print(f"   🔍 Processing {ticker}...")
                
                # Fetch Google News for this ticker
                google_result = fetch_google_news_by_ticker(ticker, 1)
                if google_result.get('status') == 'success':
                    total_articles += google_result.get('articles_new', 0)
                    total_new += google_result.get('articles_new', 0)
                    total_duplicate += google_result.get('articles_duplicate', 0)
                    sources_processed.append(f"google_news_{ticker}")
                
                # Small delay to avoid rate limiting
                time.sleep(1)
                
            except Exception as e:
                print(f"   ⚠️  Error processing {ticker}: {e}")
                continue
        
        # Update job run
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = total_articles
        job_run.details.update({
            "total_articles": total_articles,
            "new_articles": total_new,
            "duplicate_articles": total_duplicate,
            "sources_processed": sources_processed
        })
        
        db.commit()
        
        print(f"✅ RSS ingestion complete: {total_new} new, {total_duplicate} duplicate")
        
        return {
            "status": "success",
            "task_id": task_id,
            "total_articles": total_articles,
            "new_articles": total_new,
            "duplicate_articles": total_duplicate,
            "tickers_processed": len(tickers),
            "sources_processed": sources_processed
        }
        
    except Exception as e:
        print(f"❌ Error in automated RSS ingestion: {e}")
        if 'job_run' in locals():
            job_run.status = "failed"
            job_run.finished_at =datetime.utcnow()
            job_run.details.update({"error": str(e)})
            db.commit()
        raise
        
    finally:
        db.close()
