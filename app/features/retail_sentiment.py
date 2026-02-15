"""
Retail Sentiment Feature Calculator

Analyzes sentiment from retail investor sources like Reddit WallStreetBets
to provide insights into meme stock potential and retail trading patterns.
"""

from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from statistics import mean, stdev
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, String

from app.models.article import Article


@dataclass
class RetailSentimentMetrics:
    """Container for retail sentiment metrics"""
    wsb_sentiment_3d: Optional[float] = None
    wsb_sentiment_7d: Optional[float] = None
    wsb_mention_count_3d: int = 0
    wsb_mention_count_7d: int = 0
    wsb_engagement_score: Optional[float] = None
    retail_buzz_score: Optional[float] = None  # Combined metric
    meme_stock_indicator: Optional[float] = None  # 0-1 score for meme potential


class RetailSentimentFeatures:
    """Calculate retail sentiment features from WSB and other retail sources"""
    
    @staticmethod
    def calculate_for_ticker(
        db: Session, 
        ticker: str, 
        target_date: date = None
    ) -> RetailSentimentMetrics:
        """
        Calculate retail sentiment features for a specific ticker
        """
        if target_date is None:
            target_date = date.today()
        
        metrics = RetailSentimentMetrics()
        
        # Date ranges
        date_3d = target_date - timedelta(days=3)
        date_7d = target_date - timedelta(days=7)
        
        # WSB sentiment (3 days)
        wsb_3d = RetailSentimentFeatures._get_wsb_metrics(
            db, ticker, date_3d, target_date
        )
        metrics.wsb_sentiment_3d = wsb_3d.get('avg_sentiment')
        metrics.wsb_mention_count_3d = wsb_3d.get('mention_count', 0)
        
        # WSB sentiment (7 days)
        wsb_7d = RetailSentimentFeatures._get_wsb_metrics(
            db, ticker, date_7d, target_date
        )
        metrics.wsb_sentiment_7d = wsb_7d.get('avg_sentiment')
        metrics.wsb_mention_count_7d = wsb_7d.get('mention_count', 0)
        
        # Engagement score (based on Reddit scores and comments)
        metrics.wsb_engagement_score = RetailSentimentFeatures._calculate_engagement_score(
            db, ticker, date_7d, target_date
        )
        
        # Retail buzz score (combines sentiment, mentions, and engagement)
        metrics.retail_buzz_score = RetailSentimentFeatures._calculate_buzz_score(
            metrics.wsb_sentiment_7d,
            metrics.wsb_mention_count_7d,
            metrics.wsb_engagement_score
        )
        
        # Meme stock indicator
        metrics.meme_stock_indicator = RetailSentimentFeatures._calculate_meme_indicator(
            db, ticker, date_7d, target_date
        )
        
        return metrics
    
    @staticmethod
    def _get_wsb_metrics(
        db: Session, 
        ticker: str, 
        start_date: date, 
        end_date: date
    ) -> Dict:
        """Get WSB-specific metrics for a ticker in date range"""
        
        # Query WSB articles (both old and enhanced sources)
        wsb_articles = db.query(Article).filter(
            and_(
                Article.tickers.contains([ticker]),
                func.date(Article.published_at) >= start_date,
                func.date(Article.published_at) <= end_date,
                or_(
                    Article.article_metadata.cast(String).like('%"source": "reddit_wsb"%'),
                    Article.article_metadata.cast(String).like('%"source": "reddit_wsb_enhanced"%')
                )
            )
        ).all()
        
        if not wsb_articles:
            return {"avg_sentiment": None, "mention_count": 0}

        # Convert Decimal to float for calculations
        sentiments = [float(article.sentiment) for article in wsb_articles if article.sentiment is not None]

        return {
            "avg_sentiment": mean(sentiments) if sentiments else None,
            "mention_count": len(wsb_articles),
            "sentiment_std": stdev(sentiments) if len(sentiments) > 1 else 0,
            "articles": wsb_articles
        }
    
    @staticmethod
    def _calculate_engagement_score(
        db: Session,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[float]:
        """
        Calculate engagement score based on Reddit metrics
        """
        
        wsb_articles = db.query(Article).filter(
            and_(
                Article.tickers.contains([ticker]),
                func.date(Article.published_at) >= start_date,
                func.date(Article.published_at) <= end_date,
                Article.article_metadata.cast(String).like('%"source": "reddit_wsb"%')
            )
        ).all()
        
        if not wsb_articles:
            return None
        
        total_score = 0
        total_comments = 0
        
        for article in wsb_articles:
            metadata = article.article_metadata or {}
            reddit_score = metadata.get('reddit_score', 0)
            num_comments = metadata.get('num_comments', 0)
            
            # Normalize and weight the engagement
            # Reddit score (upvotes - downvotes), capped at 1000
            score_component = min(max(reddit_score, 0), 1000) / 1000.0
            
            # Comment count, capped at 500 comments
            comment_component = min(num_comments, 500) / 500.0
            
            # Combined engagement for this post
            post_engagement = (score_component * 0.6 + comment_component * 0.4)
            total_score += post_engagement
            total_comments += num_comments
        
        # Average engagement across all posts
        avg_engagement = total_score / len(wsb_articles)
        
        # Boost for high comment volume (indicates viral potential)
        comment_boost = min(total_comments / (len(wsb_articles) * 50), 2.0) / 2.0
        
        final_score = (avg_engagement * 0.8 + comment_boost * 0.2)
        return min(final_score, 1.0)
    
    @staticmethod
    def _calculate_buzz_score(
        sentiment: Optional[float],
        mention_count: int,
        engagement: Optional[float]
    ) -> Optional[float]:
        """
        Calculate overall retail buzz score (0-1)
        Combines sentiment, mention frequency, and engagement
        """
        if sentiment is None:
            return None
        
        # Mention frequency score (log scale, capped at 20 mentions)
        mention_score = min(mention_count / 20.0, 1.0)
        
        # Engagement score (already 0-1)
        engagement_score = engagement or 0.0
        
        # Sentiment deviation from neutral (0.5)
        # High positive or negative sentiment both contribute to buzz
        sentiment_intensity = abs(float(sentiment) - 0.5) * 2  # 0-1 scale
        
        # Weighted combination
        buzz_score = (
            sentiment_intensity * 0.4 +
            mention_score * 0.35 +
            engagement_score * 0.25
        )
        
        return min(buzz_score, 1.0)
    
    @staticmethod
    def _calculate_meme_indicator(
        db: Session,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> Optional[float]:
        """
        Calculate meme stock indicator based on WSB patterns
        """
        
        wsb_articles = db.query(Article).filter(
            and_(
                Article.tickers.contains([ticker]),
                func.date(Article.published_at) >= start_date,
                func.date(Article.published_at) <= end_date,
                or_(
                    Article.article_metadata.cast(String).like('%"source": "reddit_wsb"%'),
                    Article.article_metadata.cast(String).like('%"source": "reddit_wsb_enhanced"%')
                )
            )
        ).all()
        
        if not wsb_articles:
            return None
        
        meme_indicators = 0
        total_posts = len(wsb_articles)
        
        # Keywords that indicate meme stock behavior
        meme_keywords = [
            'TO THE MOON', 'ROCKET', '🚀', 'DIAMOND HANDS', 'HODL',
            'SQUEEZE', 'YOLO', 'APE', 'STONKS', 'TENDIES', 'LAMBO'
        ]
        
        for article in wsb_articles:
            text = (article.title + " " + (article.raw_content or "")).upper()
            
            # Check for meme keywords
            meme_keyword_count = sum(1 for keyword in meme_keywords if keyword in text)
            
            # Check metadata for high engagement
            metadata = article.article_metadata or {}
            reddit_score = metadata.get('reddit_score', 0)
            num_comments = metadata.get('num_comments', 0)
            
            # High engagement threshold
            high_engagement = reddit_score > 100 or num_comments > 50
            
            # Multiple ticker mentions (pump behavior)
            ticker_mentions = text.count(ticker.upper())
            multiple_mentions = ticker_mentions > 2
            
            # Calculate meme score for this post (0-1)
            post_meme_score = 0
            
            if meme_keyword_count > 0:
                post_meme_score += 0.4
            if high_engagement:
                post_meme_score += 0.3
            if multiple_mentions:
                post_meme_score += 0.2
            if article.sentiment and float(article.sentiment) > 0.7:  # Very positive sentiment
                post_meme_score += 0.1
            
            if post_meme_score > 0.5:  # Threshold for meme behavior
                meme_indicators += 1
        
        # Percentage of posts showing meme behavior
        meme_ratio = meme_indicators / total_posts
        
        # Boost for volume (many posts = more meme potential)
        volume_boost = min(total_posts / 10.0, 1.0) * 0.2
        
        final_meme_score = min(meme_ratio + volume_boost, 1.0)
        return final_meme_score
    
    @staticmethod
    def get_trending_tickers(db: Session, days: int = 7, limit: int = 20) -> List[Dict]:
        """
        Get tickers trending on WSB based on mention count and engagement
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Query for WSB articles with tickers (both old and enhanced sources)
        wsb_articles = db.query(Article).filter(
            and_(
                func.date(Article.published_at) >= start_date,
                func.date(Article.published_at) <= end_date,
                or_(
                    Article.article_metadata.cast(String).like('%"source": "reddit_wsb"%'),
                    Article.article_metadata.cast(String).like('%"source": "reddit_wsb_enhanced"%')
                ),
                Article.tickers.isnot(None),
                func.array_length(Article.tickers, 1) > 0
            )
        ).all()
        
        # Count mentions and calculate metrics per ticker
        ticker_stats = {}
        
        for article in wsb_articles:
            for ticker in article.tickers:
                if ticker not in ticker_stats:
                    ticker_stats[ticker] = {
                        'mention_count': 0,
                        'total_sentiment': 0,
                        'total_score': 0,
                        'total_comments': 0,
                        'articles': []
                    }
                
                stats = ticker_stats[ticker]
                stats['mention_count'] += 1
                stats['total_sentiment'] += float(article.sentiment) if article.sentiment else 0.5
                stats['articles'].append(article)
                
                metadata = article.article_metadata or {}
                stats['total_score'] += metadata.get('reddit_score', 0)
                stats['total_comments'] += metadata.get('num_comments', 0)
        
        # Calculate final metrics and rank
        trending_tickers = []
        
        for ticker, stats in ticker_stats.items():
            if stats['mention_count'] < 2:  # Skip tickers with too few mentions
                continue
            
            avg_sentiment = stats['total_sentiment'] / stats['mention_count']
            avg_score = stats['total_score'] / stats['mention_count']
            avg_comments = stats['total_comments'] / stats['mention_count']
            
            # Trending score combines mentions, engagement, and sentiment
            trending_score = (
                min(stats['mention_count'] / 10.0, 1.0) * 0.4 +  # Mention frequency
                min(avg_score / 100.0, 1.0) * 0.3 +              # Reddit score
                min(avg_comments / 50.0, 1.0) * 0.2 +            # Comment engagement
                abs(avg_sentiment - 0.5) * 2 * 0.1               # Sentiment intensity
            )
            
            trending_tickers.append({
                'ticker': ticker,
                'mention_count': stats['mention_count'],
                'avg_sentiment': round(avg_sentiment, 3),
                'avg_reddit_score': round(avg_score, 1),
                'avg_comments': round(avg_comments, 1),
                'trending_score': round(trending_score, 3)
            })
        
        # Sort by trending score and return top N
        trending_tickers.sort(key=lambda x: x['trending_score'], reverse=True)
        return trending_tickers[:limit]
