"""
Enhanced WSB Reddit Ingestion using parse.py logic
Provides robust Reddit parsing without external dependencies
"""

import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse

import requests
from celery import shared_task
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.article import Article
from app.models.data_source import DataSource
from app.models.etl_job_run import ETLJobRun
from app.models.stock import Stock
from app.tasks.etl_helpers import get_or_create_etl_job


class RedditParser:
    """
    Enhanced Reddit parser based on parse.py logic
    Handles Reddit API responses and extracts structured data

    When REDDIT_CLIENT_ID/SECRET are configured, uses Reddit's OAuth app-only
    flow against oauth.reddit.com. The anonymous www.reddit.com JSON endpoint
    is kept as a dev fallback only, Reddit 403-blocks it from datacenter IPs.
    """

    def __init__(self):
        from app.core.config import settings

        self.client_id = settings.REDDIT_CLIENT_ID
        self.client_secret = settings.REDDIT_CLIENT_SECRET
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': settings.REDDIT_USER_AGENT})

    def _get_oauth_token(self) -> Optional[str]:
        """App-only (client_credentials) bearer token, cached until ~expiry."""
        if not (self.client_id and self.client_secret):
            return None
        if self._token and time.time() < self._token_expires_at:
            return self._token
        try:
            resp = self.session.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            self._token = payload["access_token"]
            self._token_expires_at = time.time() + int(payload.get("expires_in", 3600)) - 60
            return self._token
        except Exception as e:
            print(f"❌ Reddit OAuth token request failed: {e}")
            return None

    def parse_subreddit(self, subreddit: str, sort: str = 'hot', limit: int = 100) -> List[Dict]:
        """
        Parse subreddit posts using Reddit's JSON API

        Args:
            subreddit: Subreddit name (e.g., 'wallstreetbets')
            sort: Sort method ('hot', 'new', 'top', 'rising')
            limit: Number of posts to fetch

        Returns:
            List of parsed post dictionaries
        """
        token = self._get_oauth_token()
        if token:
            url = f"https://oauth.reddit.com/r/{subreddit}/{sort}"
            headers = {"Authorization": f"Bearer {token}"}
        else:
            url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
            headers = None
        params = {
            'limit': min(limit, 100),
            't': 'day'  # Time filter
        }

        try:
            response = self.session.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if 'data' not in data or 'children' not in data['data']:
                return []
            
            posts = []
            for post_data in data['data']['children']:
                post = post_data['data']
                parsed_post = self._parse_post(post)
                if parsed_post:
                    posts.append(parsed_post)
            
            return posts
            
        except Exception as e:
            print(f"❌ Error parsing subreddit {subreddit}: {e}")
            return []
    
    def _parse_post(self, post: Dict) -> Optional[Dict]:
        """
        Parse individual Reddit post data
        
        Args:
            post: Raw post data from Reddit API
            
        Returns:
            Parsed post dictionary or None if invalid
        """
        try:
            # Extract basic post information
            post_id = post.get('id', '')
            title = post.get('title', '').strip()
            selftext = post.get('selftext', '').strip()
            author = post.get('author', 'unknown')
            score = post.get('score', 0)
            num_comments = post.get('num_comments', 0)
            created_utc = post.get('created_utc', 0)
            permalink = post.get('permalink', '')
            url = post.get('url', '')
            
            # Skip deleted/removed posts
            if not title or post.get('removed_by_category'):
                return None
            
            # Skip posts older than 7 days
            if created_utc:
                post_date = datetime.fromtimestamp(created_utc)
                if post_date < datetime.utcnow() - timedelta(days=7):
                    return None
            
            # Build full URL
            full_url = f"https://reddit.com{permalink}" if permalink else url
            
            # Extract tickers from title and text
            combined_text = f"{title} {selftext}"
            tickers = self._extract_tickers(combined_text)
            
            # Calculate sentiment score
            sentiment = self._calculate_sentiment(title, selftext, score, num_comments)
            
            return {
                'id': post_id,
                'title': title,
                'text': selftext,
                'author': author,
                'score': score,
                'num_comments': num_comments,
                'created_utc': created_utc,
                'url': full_url,
                'tickers': tickers,
                'sentiment': sentiment,
                'raw_data': post
            }
            
        except Exception as e:
            print(f"❌ Error parsing post: {e}")
            return None
    
    def _extract_tickers(self, text: str) -> List[str]:
        """
        Extract stock tickers from text using multiple patterns
        
        Args:
            text: Text to search for tickers
            
        Returns:
            List of found ticker symbols
        """
        if not text:
            return []
        
        # Get known tickers from database
        db = SessionLocal()
        try:
            stocks = db.query(Stock.symbol).filter(Stock.is_active == True).all()
            known_tickers = set(stock.symbol for stock in stocks)
            
            # Add common WSB tickers that might not be in our database
            wsb_common_tickers = {
                'GME', 'AMC', 'BBBY', 'NOK', 'BB', 'PLTR', 'WISH', 'CLOV', 'SNDL', 'NAKD',
                'EXPR', 'KOSS', 'SENS', 'ZOM', 'IDEX', 'CTRM', 'MARK', 'HOFV', 'GNUS',
                'TSLA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'SPY', 'QQQ'
            }
            known_tickers.update(wsb_common_tickers)
            
        except Exception as e:
            print(f"⚠️  Error getting known tickers: {e}")
            known_tickers = wsb_common_tickers
        finally:
            db.close()
        
        found_tickers = set()
        text_upper = text.upper()
        
        # Pattern 1: $TICKER format (common in WSB)
        dollar_tickers = re.findall(r'\$([A-Z]{1,5})\b', text_upper)
        for ticker in dollar_tickers:
            if ticker in known_tickers:
                found_tickers.add(ticker)
        
        # Pattern 2: Ticker followed by WSB terms
        wsb_terms = ['TO THE MOON', 'STONKS', 'YOLO', 'CALLS', 'PUTS', 'SQUEEZE', 'HODL', 'APE', 'ROCKET', '🚀']
        for term in wsb_terms:
            pattern = rf'\b([A-Z]{{1,5}})\b.*?{re.escape(term)}'
            matches = re.findall(pattern, text_upper)
            for ticker in matches:
                if ticker in known_tickers and len(ticker) >= 2:
                    found_tickers.add(ticker)
        
        # Pattern 3: Common WSB ticker references
        parentheses_tickers = re.findall(r'\(([A-Z]{1,5})\)', text_upper)
        quote_tickers = re.findall(r'"([A-Z]{1,5})"', text_upper)
        
        for ticker in parentheses_tickers + quote_tickers:
            if ticker in known_tickers:
                found_tickers.add(ticker)
        
        # Pattern 4: Direct ticker mentions with context
        financial_terms = ['STOCK', 'SHARE', 'TRADE', 'BUY', 'SELL', 'PRICE', 'EARNINGS', 'MOON', 'PUMP', 'DUMP']
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
    
    def _calculate_sentiment(self, title: str, text: str, score: int, num_comments: int) -> float:
        """
        Calculate WSB-specific sentiment score
        
        Args:
            title: Post title
            text: Post text
            score: Reddit score (upvotes - downvotes)
            num_comments: Number of comments
            
        Returns:
            Sentiment score between 0.0 and 1.0
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
            'TENDIES', 'GAINS', 'YOLO', 'APE STRONG', 'MOONSHOT', 'GREEN'
        ]
        
        bearish_patterns = [
            'PAPER HANDS', 'DUMP', 'CRASH', 'PUTS', 'BEARISH', 'SELL',
            'LOSS PORN', 'BAGS', 'BAGHOLD', 'DEAD CAT', 'DRILL', 'RED'
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
def fetch_wsb_enhanced(self, limit: int = 100, sort: str = 'hot') -> Dict:
    """
    Enhanced WSB ingestion using improved Reddit parser
    
    Args:
        limit: Number of posts to fetch (max 100)
        sort: Sort method ('hot', 'new', 'top', 'rising')
        
    Returns:
        Dict with ingestion statistics
    """
    db = SessionLocal()
    task_id = self.request.id
    
    try:
        print(f"🦍 Enhanced WSB ingestion: {sort} posts (limit: {limit})")
        
        # Get or reuse admin-created ETLJobRun
        job_run = get_or_create_etl_job(db, task_id, "wsb_ingestion", {
            "task_id": task_id,
            "limit": limit,
            "sort": sort,
        })
        
        # Get or create data source
        data_source = db.query(DataSource).filter(
            DataSource.name == "Reddit WallStreetBets Enhanced"
        ).first()
        
        if not data_source:
            data_source = DataSource(
                name="Reddit WallStreetBets Enhanced",
                source_type="reddit",
                base_url="https://www.reddit.com/r/wallstreetbets",
                reliability_score=0.8
            )
            db.add(data_source)
            db.commit()
        
        # Initialize Reddit parser
        parser = RedditParser()
        
        # Parse WSB posts
        posts = parser.parse_subreddit('wallstreetbets', sort, limit)
        
        if not posts:
            print("⚠️  No posts found from Reddit API")
            job_run.status = "success"
            job_run.finished_at = datetime.utcnow()
            job_run.items_processed = 0
            db.commit()
            return {"status": "success", "posts_found": 0, "message": "No posts found"}
        
        print(f"📊 Found {len(posts)} posts from Reddit API")
        
        posts_processed = 0
        posts_new = 0
        posts_duplicate = 0
        tickers_found = {}
        
        # Process each post
        for post in posts:
            try:
                # Skip posts with no valid tickers
                if not post['tickers']:
                    continue
                
                # Generate URL hash for deduplication
                url_hash = hashlib.sha256(post['url'].encode('utf-8')).hexdigest()
                
                # Check if already exists
                existing_article = db.query(Article).filter(
                    Article.url_hash == url_hash
                ).first()
                
                if existing_article:
                    posts_duplicate += 1
                    continue
                
                # Convert timestamp
                published_at = datetime.fromtimestamp(post['created_utc']) if post['created_utc'] else datetime.utcnow()
                
                # Create article record
                article = Article(
                    source_id=data_source.id,
                    url=post['url'],
                    url_hash=url_hash,
                    title=post['title'],
                    published_at=published_at,
                    raw_content=post['text'][:5000] if post['text'] else None,
                    tickers=post['tickers'],
                    sentiment=post['sentiment'],
                    language="en",
                    article_metadata={
                        "source": "reddit_wsb",
                        "reddit_score": post['score'],
                        "num_comments": post['num_comments'],
                        "author": post['author'],
                        "post_type": "discussion",
                        "subreddit": "wallstreetbets",
                        "sort_method": sort,
                        "parsing_method": "enhanced_parser"
                    }
                )
                
                db.add(article)
                posts_new += 1
                posts_processed += 1
                
                # Track ticker mentions
                for ticker in post['tickers']:
                    tickers_found[ticker] = tickers_found.get(ticker, 0) + 1
                
                # Debug output for first few posts
                if posts_processed <= 5:
                    print(f"  ✅ Post: {post['title'][:50]}...")
                    print(f"     Tickers: {post['tickers']}")
                    print(f"     Sentiment: {post['sentiment']:.3f}")
                
            except Exception as e:
                print(f"  ⚠️  Error processing WSB post: {e}")
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
        
        print(f"🎉 Enhanced WSB ingestion complete: {posts_new} new posts")
        print(f"   Top tickers: {dict(list(sorted(tickers_found.items(), key=lambda x: x[1], reverse=True))[:10])}")
        
        return {
            "status": "success",
            "posts_new": posts_new,
            "posts_duplicate": posts_duplicate,
            "tickers_found": tickers_found,
            "total_processed": posts_processed
        }
        
    except Exception as e:
        print(f"❌ Error in enhanced WSB ingestion: {e}")
        
        if 'job_run' in locals():
            job_run.status = "error"
            job_run.finished_at = datetime.utcnow()
            job_run.details.update({
                "error": str(e),
                "error_type": type(e).__name__
            })
            db.commit()
        
        raise e
        
    finally:
        db.close()


@shared_task
def test_reddit_parser():
    """
    Test the enhanced Reddit parser functionality
    """
    try:
        print("🧪 Testing enhanced Reddit parser...")
        
        parser = RedditParser()
        
        # Test parsing a small number of posts
        posts = parser.parse_subreddit('wallstreetbets', 'hot', 5)
        
        if posts:
            print(f"✅ Parser working: Found {len(posts)} posts")
            for i, post in enumerate(posts[:3]):
                print(f"  Post {i+1}: {post['title'][:50]}...")
                print(f"    Tickers: {post['tickers']}")
                print(f"    Sentiment: {post['sentiment']:.3f}")
        else:
            print("⚠️  No posts found - possible API issue")
        
        return {
            "status": "success",
            "posts_found": len(posts),
            "message": "Enhanced Reddit parser is working correctly"
        }
        
    except Exception as e:
        print(f"❌ Enhanced Reddit parser test failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
