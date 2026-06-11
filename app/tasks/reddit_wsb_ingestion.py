"""
WallStreetBets Reddit Ingestion Task

Fetches hot posts from r/wallstreetbets to capture retail investor sentiment
and identify trending stocks. Provides valuable insight into meme stock movements
and retail trading patterns.
"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import requests
from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.article import Article
from app.models.data_source import DataSource
from app.models.etl_job_run import ETLJobRun
from app.models.stock import Stock


class WSBIngestionError(Exception):
    """Custom exception for WSB ingestion errors"""
    pass


def extract_tickers_from_wsb_text(text: str, known_tickers: Set[str]) -> List[str]:
    """
    Extract stock tickers from WSB text using WSB-specific patterns
    
    WSB users often use:
    - $TICKER format
    - TICKER followed by specific terms
    - Common abbreviations and slang
    """
    if not text:
        return []
    
    found_tickers = set()
    text_upper = text.upper()
    
    # Pattern 1: $TICKER format (common in WSB)
    dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text_upper)
    for ticker in dollar_tickers:
        if ticker in known_tickers:
            found_tickers.add(ticker)
    
    # Pattern 2: Ticker followed by WSB terms
    wsb_terms = ['TO THE MOON', 'STONKS', 'YOLO', 'CALLS', 'PUTS', 'SQUEEZE', 'HODL', 'APE']
    for term in wsb_terms:
        # Look for tickers mentioned near these terms
        pattern = rf'\b([A-Z]{{1,5}})\b.*?{re.escape(term)}'
        matches = re.findall(pattern, text_upper)
        for ticker in matches:
            if ticker in known_tickers and len(ticker) >= 2:
                found_tickers.add(ticker)
    
    # Pattern 3: Common WSB ticker references
    # Look for tickers in parentheses or quotes
    parentheses_tickers = re.findall(r'\(([A-Z]{1,5})\)', text_upper)
    quote_tickers = re.findall(r'"([A-Z]{1,5})"', text_upper)
    
    for ticker in parentheses_tickers + quote_tickers:
        if ticker in known_tickers:
            found_tickers.add(ticker)
    
    # Pattern 4: Direct ticker mentions (more conservative)
    # Only include if they appear multiple times or with financial terms
    financial_terms = ['STOCK', 'SHARE', 'TRADE', 'BUY', 'SELL', 'PRICE', 'EARNINGS']
    words = re.findall(r'\b[A-Z]{2,5}\b', text_upper)
    word_counts = {}
    for word in words:
        if word in known_tickers:
            word_counts[word] = word_counts.get(word, 0) + 1
    
    # Include tickers mentioned multiple times or near financial terms
    for ticker, count in word_counts.items():
        if count >= 2 or any(term in text_upper for term in financial_terms):
            found_tickers.add(ticker)
    
    return list(found_tickers)[:10]  # Limit to prevent spam


def calculate_wsb_sentiment_score(title: str, text: str, score: int, num_comments: int) -> float:
    """
    Calculate WSB-specific sentiment score combining:
    - Reddit score (upvotes - downvotes)
    - Comment count (engagement)
    - WSB-specific keywords
    """
    
    # Base sentiment from Reddit score
    # Normalize score to 0-1 range (most WSB posts range from -100 to 10000)
    normalized_score = max(0, min(score / 1000.0, 10)) / 10.0
    
    # Engagement factor from comments
    engagement_factor = min(num_comments / 100.0, 5) / 5.0  # 0-1 scale
    
    # WSB sentiment keywords
    combined_text = (title + " " + text).upper()
    
    bullish_patterns = [
        'TO THE MOON', 'ROCKET', '🚀', 'DIAMOND HANDS', 'HODL', 'BULLISH',
        'SQUEEZE', 'PUMP', 'CALLS', 'BUY THE DIP', 'STONKS', 'LAMBO',
        'TENDIES', 'GAINS', 'YOLO', 'APE STRONG'
    ]
    
    bearish_patterns = [
        'PAPER HANDS', 'DUMP', 'CRASH', 'PUTS', 'BEARISH', 'SELL',
        'LOSS PORN', 'BAGS', 'BAGHOLD', 'DEAD CAT', 'DRILL'
    ]
    
    bullish_count = sum(1 for pattern in bullish_patterns if pattern in combined_text)
    bearish_count = sum(1 for pattern in bearish_patterns if pattern in combined_text)
    
    # Keyword sentiment (0-1)
    total_keywords = bullish_count + bearish_count
    keyword_sentiment = 0.5  # neutral default
    if total_keywords > 0:
        keyword_sentiment = bullish_count / total_keywords
    
    # Weighted combination
    final_sentiment = (
        normalized_score * 0.4 +      # Reddit score weight
        engagement_factor * 0.2 +     # Comment engagement weight  
        keyword_sentiment * 0.4       # WSB keywords weight
    )
    
    return max(0.0, min(1.0, final_sentiment))


@shared_task(bind=True)
def fetch_wsb_hot_posts(self, limit: int = 100, time_filter: str = "day") -> Dict:
    """
    Fetch hot posts from r/wallstreetbets
    
    Args:
        limit: Number of posts to fetch (max 100)
        time_filter: "hour", "day", "week", "month", "year", "all"
        
    Returns:
        Dict with ingestion statistics
    """
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        print(f"🦍 Fetching WSB hot posts (limit: {limit}, filter: {time_filter})")
        
        # Reddit API endpoint (using public JSON API, no auth required)
        reddit_url = f"https://www.reddit.com/r/wallstreetbets/hot.json"
        
        # Get or create data source
        data_source = db.query(DataSource).filter(
            DataSource.base_url == reddit_url
        ).first()
        
        if not data_source:
            data_source = DataSource(
                name="Reddit WallStreetBets",
                source_type="reddit",
                base_url=reddit_url,
                reliability_score=0.7  # Medium - retail sentiment can be noisy but valuable
            )
            db.add(data_source)
            db.flush()
        
        # Create ETL job run
        job_run = ETLJobRun(
            job_name="wsb_hot_posts",
            status="running",
            started_at=datetime.utcnow(),
            details={
                "task_id": task_id,
                "limit": limit,
                "time_filter": time_filter
            }
        )
        db.add(job_run)
        db.commit()
        
        # Get known tickers for validation
        stocks = db.query(Stock.symbol).all()
        known_tickers = set(stock.symbol for stock in stocks)
        
        # Add some common WSB tickers that might not be in our database
        wsb_common_tickers = {
            'GME', 'AMC', 'BBBY', 'NOK', 'BB', 'PLTR', 'WISH', 'CLOV', 'SNDL', 'NAKD',
            'EXPR', 'KOSS', 'SENS', 'ZOM', 'IDEX', 'CTRM', 'MARK', 'HOFV', 'GNUS'
        }
        known_tickers.update(wsb_common_tickers)
        
        # Fetch Reddit data
        headers = {
            'User-Agent': 'Stonks-Analytics/1.0 (Educational Research)'
        }
        
        params = {
            'limit': min(limit, 100),
            't': time_filter
        }
        
        try:
            response = requests.get(reddit_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise WSBIngestionError(f"Failed to fetch WSB data: {e}")
        
        if 'data' not in data or 'children' not in data['data']:
            raise WSBIngestionError("Invalid Reddit API response format")
        
        posts_processed = 0
        posts_new = 0
        posts_duplicate = 0
        tickers_found = {}
        
        for post_data in data['data']['children']:
            try:
                post = post_data['data']
                
                # Extract post details
                title = post.get('title', '')
                selftext = post.get('selftext', '')
                url = f"https://reddit.com{post.get('permalink', '')}"
                score = post.get('score', 0)
                num_comments = post.get('num_comments', 0)
                created_utc = post.get('created_utc', 0)
                author = post.get('author', 'unknown')
                
                # Skip deleted/removed posts
                if not title or post.get('removed_by_category'):
                    continue
                
                # Convert timestamp
                published_at = datetime.fromtimestamp(created_utc) if created_utc else None
                
                # Skip old posts (older than 7 days)
                if published_at and published_at < datetime.utcnow() - timedelta(days=7):
                    continue
                
                # Generate URL hash for deduplication
                url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
                
                # Check if already exists
                existing_article = db.query(Article).filter(
                    Article.url_hash == url_hash
                ).first()
                
                if existing_article:
                    posts_duplicate += 1
                    continue
                
                # Extract tickers
                extracted_tickers = extract_tickers_from_wsb_text(
                    title + " " + selftext, 
                    known_tickers
                )
                
                # Debug: print what we found
                if posts_processed < 5:  # Only debug first few posts
                    print(f"   Post: {title[:50]}...")
                    print(f"   Text preview: {(title + ' ' + selftext)[:100]}...")
                    print(f"   Extracted tickers: {extracted_tickers}")
                    print(f"   Known tickers count: {len(known_tickers)}")
                
                # Skip posts with no valid tickers
                if not extracted_tickers:
                    continue
                
                # Calculate WSB-specific sentiment
                sentiment_score = calculate_wsb_sentiment_score(
                    title, selftext, score, num_comments
                )
                
                # Track ticker mentions
                for ticker in extracted_tickers:
                    tickers_found[ticker] = tickers_found.get(ticker, 0) + 1
                
                # Create article record
                article = Article(
                    source_id=data_source.id,
                    url=url,
                    url_hash=url_hash,
                    title=title,
                    published_at=published_at,
                    raw_content=selftext[:5000] if selftext else None,  # Limit length
                    tickers=extracted_tickers,
                    sentiment=sentiment_score,
                    language="en",
                    article_metadata={
                        "source": "reddit_wsb",
                        "reddit_score": score,
                        "num_comments": num_comments,
                        "author": author,
                        "post_type": "discussion",
                        "subreddit": "wallstreetbets"
                    }
                )
                
                db.add(article)
                posts_new += 1
                posts_processed += 1
                
            except Exception as e:
                print(f"   ⚠️  Error processing WSB post: {e}")
                db.rollback()
                continue
        
        db.commit()
        
        # Update job run
        job_run.status = "success"
        job_run.finished_at = datetime.utcnow()
        job_run.items_processed = posts_new
        job_run.details.update({
            "posts_new": posts_new,
            "posts_duplicate": posts_duplicate,
            "tickers_found": tickers_found,
            "total_processed": posts_processed
        })
        db.commit()
        
        print(f"✅ WSB ingestion complete: {posts_new} new posts")
        print(f"   Top tickers: {dict(list(sorted(tickers_found.items(), key=lambda x: x[1], reverse=True))[:10])}")
        
        return {
            "status": "success",
            "posts_new": posts_new,
            "posts_duplicate": posts_duplicate,
            "tickers_found": tickers_found
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
        print(f"❌ Error in WSB ingestion: {e}")
        raise
        
    finally:
        db.close()


@shared_task(bind=True)
def fetch_wsb_daily_thread(self) -> Dict:
    """
    Fetch the daily discussion thread from WSB for general market sentiment
    """
    db = SessionLocal()
    
    try:
        print("💬 Fetching WSB daily discussion thread")
        
        # Get today's daily thread
        reddit_url = "https://www.reddit.com/r/wallstreetbets/search.json"
        headers = {
            'User-Agent': 'Stonks-Analytics/1.0 (Educational Research)'
        }
        
        params = {
            'q': 'Daily Discussion Thread',
            'restrict_sr': '1',
            'sort': 'new',
            'limit': 5
        }
        
        response = requests.get(reddit_url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if 'data' not in data or 'children' not in data['data']:
            return {"status": "error", "error": "No daily thread found"}
        
        # Find today's thread
        today = datetime.utcnow().date()
        daily_thread = None
        
        for post_data in data['data']['children']:
            post = post_data['data']
            title = post.get('title', '').lower()
            created_utc = post.get('created_utc', 0)
            post_date = datetime.fromtimestamp(created_utc).date() if created_utc else None
            
            if 'daily discussion' in title and post_date == today:
                daily_thread = post
                break
        
        if not daily_thread:
            return {"status": "no_thread", "message": "No daily thread found for today"}
        
        # Get or create data source
        source_name = "Reddit WSB Daily"
        data_source = db.query(DataSource).filter(
            DataSource.name == source_name
        ).first()
        
        if not data_source:
            data_source = DataSource(
                name=source_name,
                source_type="reddit",
                base_url="https://reddit.com/r/wallstreetbets",
                reliability_score=0.6  # Daily threads are more general sentiment
            )
            db.add(data_source)
            db.flush()
        
        # Create article for daily sentiment
        url = f"https://reddit.com{daily_thread.get('permalink', '')}"
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        
        # Check if already exists
        existing = db.query(Article).filter(
            Article.url_hash == url_hash
        ).first()
        
        if existing:
            return {"status": "duplicate", "message": "Daily thread already processed"}
        
        # Calculate general market sentiment from title and any text
        title = daily_thread.get('title', '')
        selftext = daily_thread.get('selftext', '')
        score = daily_thread.get('score', 0)
        num_comments = daily_thread.get('num_comments', 0)
        
        sentiment_score = calculate_wsb_sentiment_score(title, selftext, score, num_comments)
        
        article = Article(
            source_id=data_source.id,
            url=url,
            url_hash=url_hash,
            title=title,
            published_at=datetime.fromtimestamp(daily_thread.get('created_utc', 0)),
            raw_content=selftext[:1000] if selftext else None,
            tickers=[],  # General market sentiment, no specific tickers
            sentiment=sentiment_score,
            language="en",
            article_metadata={
                "source": "reddit_wsb_daily",
                "reddit_score": score,
                "num_comments": num_comments,
                "post_type": "daily_discussion",
                "subreddit": "wallstreetbets"
            }
        )
        
        db.add(article)
        db.commit()
        
        print(f"✅ WSB daily thread processed: sentiment {sentiment_score:.2f}")
        
        return {
            "status": "success",
            "sentiment_score": sentiment_score,
            "reddit_score": score,
            "num_comments": num_comments
        }
        
    except Exception as e:
        print(f"❌ Error fetching WSB daily thread: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()
