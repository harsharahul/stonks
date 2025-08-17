#!/usr/bin/env python3
"""
Test RSS ingestion directly without Celery
"""

import sys
import os
import hashlib
import re
import requests
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models import Article, DataSource, Stock
from app.models.doc_entity import DocEntity


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


def extract_tickers_basic(text: str) -> list:
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


def test_single_rss_source(db, source_config):
    """Test fetching from a single RSS source"""
    
    source_name = source_config["name"]
    source_url = source_config["url"]
    
    print(f"📰 Fetching RSS feed: {source_name}")
    print(f"   URL: {source_url}")
    
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
        print(f"   ✅ Created data source: {source_name}")
    else:
        print(f"   ✅ Using existing data source: {source_name}")
    
    # Fetch RSS feed with timeout and user agent
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; Stonks-Analytics/1.0)'
    }
    
    try:
        print(f"   🔄 Fetching RSS feed...")
        response = requests.get(source_url, headers=headers, timeout=30)
        response.raise_for_status()
        print(f"   ✅ RSS feed fetched successfully ({len(response.content)} bytes)")
    except requests.RequestException as e:
        print(f"   ❌ Failed to fetch RSS feed: {e}")
        return {"status": "error", "error": str(e)}
    
    # Parse RSS feed
    print(f"   🔄 Parsing RSS feed...")
    feed = feedparser.parse(response.content)
    
    if feed.bozo:
        print(f"   ⚠️  RSS feed parsing warning: {feed.bozo_exception}")
    
    print(f"   ✅ RSS feed parsed: {len(feed.entries)} entries found")
    print(f"   📰 Feed title: {feed.feed.get('title', 'No title')}")
    
    # Process articles
    articles_processed = 0
    articles_new = 0
    articles_duplicate = 0
    articles_with_tickers = 0
    
    for i, entry in enumerate(feed.entries[:5], 1):  # Limit to first 5 for testing
        try:
            print(f"   📄 Processing article {i}/{min(5, len(feed.entries))}")
            
            # Extract article data
            title = clean_text(entry.get('title', ''))
            url = entry.get('link', '')
            
            if not url or not title:
                print(f"      ⚠️  Skipping - missing URL or title")
                continue
            
            print(f"      Title: {title[:60]}...")
            
            # Generate URL hash for deduplication
            url_hash = generate_url_hash(url)
            
            # Check if article already exists
            existing = db.query(Article).filter(Article.url_hash == url_hash).first()
            if existing:
                print(f"      ♻️  Duplicate article (already exists)")
                articles_duplicate += 1
                continue
            
            # Extract published date
            published_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published_at = datetime(*entry.updated_parsed[:6])
            
            print(f"      Published: {published_at}")
            
            # Extract content
            content = ""
            if hasattr(entry, 'content') and entry.content:
                content = entry.content[0].value if entry.content else ""
            elif hasattr(entry, 'summary'):
                content = entry.summary
            elif hasattr(entry, 'description'):
                content = entry.description
            
            # Clean content
            raw_content = extract_text_from_html(content)
            print(f"      Content length: {len(raw_content)} chars")
            
            # Extract tickers
            full_text = f"{title} {raw_content}"
            tickers = extract_tickers_basic(full_text)
            print(f"      Extracted tickers: {tickers}")
            
            # Create article record
            article = Article(
                source_id=data_source.id,
                url=url,
                url_hash=url_hash,
                title=title,
                published_at=published_at,
                raw_content=raw_content,
                tickers=tickers if tickers else None,
                language="en"  # Assume English for now
            )
            
            db.add(article)
            db.flush()
            
            # Create entity links for extracted tickers
            entity_count = 0
            for ticker in tickers:
                # Check if ticker exists in our stocks table
                stock_exists = db.query(Stock).filter(Stock.symbol == ticker).first()
                if stock_exists:
                    entity = DocEntity(
                        doc_id=article.id,
                        ticker=ticker,
                        company_name=stock_exists.company_name,
                        confidence=0.8,  # Basic confidence for regex extraction
                        method="rss_regex"
                    )
                    db.add(entity)
                    entity_count += 1
                    print(f"      📎 Created entity link: {ticker} -> {stock_exists.company_name}")
            
            if tickers:
                articles_with_tickers += 1
            
            articles_new += 1
            articles_processed += 1
            print(f"      ✅ Article processed successfully ({entity_count} entity links)")
            
        except Exception as e:
            print(f"      ❌ Error processing article: {e}")
            continue
    
    # Commit articles
    db.commit()
    print(f"   💾 Committed {articles_new} new articles to database")
    
    return {
        "status": "success",
        "source_name": source_name,
        "articles_new": articles_new,
        "articles_duplicate": articles_duplicate, 
        "articles_processed": articles_processed,
        "articles_with_tickers": articles_with_tickers,
        "feed_entries_total": len(feed.entries)
    }


def test_rss_direct():
    """Test RSS ingestion directly"""
    
    # Test sources (use first 2 for testing)
    test_sources = [
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
        }
    ]
    
    db = SessionLocal()
    
    try:
        print("🧪 Testing RSS ingestion (direct mode)")
        print(f"📊 Testing {len(test_sources)} RSS sources\n")
        
        # Count existing data
        initial_articles = db.query(Article).count()
        initial_entities = db.query(DocEntity).count()
        initial_sources = db.query(DataSource).count()
        
        print(f"📊 Initial counts:")
        print(f"   Articles: {initial_articles}")
        print(f"   Entity links: {initial_entities}")
        print(f"   Data sources: {initial_sources}")
        print()
        
        # Test each source
        results = []
        for i, source_config in enumerate(test_sources, 1):
            print(f"🔄 Testing source {i}/{len(test_sources)}")
            
            try:
                result = test_single_rss_source(db, source_config)
                results.append(result)
                print(f"✅ Source {i} completed: {result['articles_new']} new articles\n")
                
            except Exception as e:
                print(f"❌ Source {i} failed: {e}\n")
                results.append({"status": "error", "error": str(e)})
        
        # Final counts
        final_articles = db.query(Article).count()
        final_entities = db.query(DocEntity).count()
        final_sources = db.query(DataSource).count()
        
        print(f"📊 Final counts:")
        print(f"   Articles: {final_articles} (+{final_articles - initial_articles})")
        print(f"   Entity links: {final_entities} (+{final_entities - initial_entities})")
        print(f"   Data sources: {final_sources} (+{final_sources - initial_sources})")
        print()
        
        # Summary
        successful_sources = sum(1 for r in results if r.get("status") == "success")
        total_new_articles = sum(r.get("articles_new", 0) for r in results if r.get("status") == "success")
        total_with_tickers = sum(r.get("articles_with_tickers", 0) for r in results if r.get("status") == "success")
        
        print(f"🎉 RSS ingestion test summary:")
        print(f"   Successful sources: {successful_sources}/{len(test_sources)}")
        print(f"   Total new articles: {total_new_articles}")
        print(f"   Articles with tickers: {total_with_tickers}")
        
        # Show sample articles
        if total_new_articles > 0:
            print(f"\n📰 Sample articles:")
            recent_articles = db.query(Article).order_by(Article.id.desc()).limit(3).all()
            
            for article in recent_articles:
                print(f"   • {article.title}")
                print(f"     Tickers: {article.tickers}")
                print(f"     Published: {article.published_at}")
                
                # Show entity links
                entities = db.query(DocEntity).filter(DocEntity.doc_id == article.id).all()
                if entities:
                    print(f"     Entity links: {[f'{e.ticker}({e.confidence})' for e in entities]}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ Error in RSS ingestion test: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    test_rss_direct()
