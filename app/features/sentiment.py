"""
Sentiment feature calculators for deterministic analytics
"""

from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from statistics import mean, stdev
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.doc_entity import DocEntity


@dataclass
class SentimentMetrics:
    """Container for sentiment metrics"""
    mean_3d: Optional[float] = None
    mean_7d: Optional[float] = None
    mean_10d: Optional[float] = None
    shock: Optional[float] = None  # z-score vs baseline
    volume_weighted: Optional[float] = None
    article_count: int = 0


class SentimentFeatures:
    """Sentiment aggregation and shock detection"""
    
    @staticmethod
    def calculate_for_ticker(
        db: Session, 
        ticker: str, 
        target_date: date,
        baseline_days: int = 90
    ) -> SentimentMetrics:
        """
        Calculate sentiment features for a ticker on a specific date
        
        Args:
            db: Database session
            ticker: Stock ticker symbol
            target_date: Date to calculate features for
            baseline_days: Days to use for shock calculation baseline
            
        Returns:
            SentimentMetrics with aggregated sentiment features
        """
        
        # Get all articles with sentiment for this ticker
        end_date = target_date
        start_date = target_date - timedelta(days=baseline_days)
        
        # Query articles with entity links and sentiment
        articles_query = db.query(Article).join(DocEntity).filter(
            DocEntity.ticker == ticker,
            Article.sentiment.isnot(None),
            Article.published_at >= start_date,
            Article.published_at <= end_date
        ).order_by(Article.published_at.desc())
        
        articles = articles_query.all()
        
        if not articles:
            return SentimentMetrics()
        
        # Separate recent vs baseline periods
        recent_10d = target_date - timedelta(days=10)
        recent_7d = target_date - timedelta(days=7)
        recent_3d = target_date - timedelta(days=3)
        
        recent_3d_articles = [a for a in articles if a.published_at.date() >= recent_3d]
        recent_7d_articles = [a for a in articles if a.published_at.date() >= recent_7d]
        recent_10d_articles = [a for a in articles if a.published_at.date() >= recent_10d]
        baseline_articles = [a for a in articles if a.published_at.date() < recent_10d]
        
        metrics = SentimentMetrics()
        
        # Calculate mean sentiments
        if recent_3d_articles:
            metrics.mean_3d = mean([float(a.sentiment) for a in recent_3d_articles])
        
        if recent_7d_articles:
            metrics.mean_7d = mean([float(a.sentiment) for a in recent_7d_articles])
            metrics.article_count = len(recent_7d_articles)
        
        if recent_10d_articles:
            metrics.mean_10d = mean([float(a.sentiment) for a in recent_10d_articles])
        
        # Calculate volume-weighted sentiment (weight by days from target_date)
        if recent_7d_articles:
            weighted_sum = 0.0
            weight_sum = 0.0
            
            for article in recent_7d_articles:
                days_ago = (target_date - article.published_at.date()).days
                weight = max(1.0, 8.0 - days_ago)  # More recent = higher weight
                weighted_sum += float(article.sentiment) * weight
                weight_sum += weight
            
            if weight_sum > 0:
                metrics.volume_weighted = weighted_sum / weight_sum
        
        # Calculate sentiment shock (z-score vs baseline)
        if baseline_articles and recent_7d_articles and len(baseline_articles) > 5:
            baseline_sentiments = [float(a.sentiment) for a in baseline_articles]
            recent_mean = metrics.mean_7d
            
            if len(baseline_sentiments) > 1:
                baseline_mean = mean(baseline_sentiments)
                baseline_std = stdev(baseline_sentiments)
                
                if baseline_std > 0:
                    metrics.shock = (recent_mean - baseline_mean) / baseline_std
        
        return metrics
    
    @staticmethod
    def calculate_bulk(
        db: Session,
        tickers: List[str],
        target_date: date
    ) -> Dict[str, SentimentMetrics]:
        """
        Calculate sentiment features for multiple tickers efficiently
        
        Args:
            db: Database session
            tickers: List of ticker symbols
            target_date: Date to calculate features for
            
        Returns:
            Dictionary mapping ticker -> SentimentMetrics
        """
        results = {}
        
        # TODO: Optimize with bulk queries when we have more data
        for ticker in tickers:
            results[ticker] = SentimentFeatures.calculate_for_ticker(
                db, ticker, target_date
            )
        
        return results
    
    @staticmethod
    def get_sentiment_distribution(db: Session, days: int = 30) -> Dict[str, float]:
        """
        Get overall sentiment distribution for normalization
        
        Args:
            db: Database session
            days: Number of days to analyze
            
        Returns:
            Dictionary with sentiment statistics
        """
        cutoff_date = date.today() - timedelta(days=days)
        
        sentiments = db.query(Article.sentiment).filter(
            Article.sentiment.isnot(None),
            Article.published_at >= cutoff_date
        ).all()
        
        if not sentiments:
            return {"mean": 0.0, "std": 1.0, "count": 0}
        
        sentiment_values = [float(s[0]) for s in sentiments]
        
        return {
            "mean": mean(sentiment_values),
            "std": stdev(sentiment_values) if len(sentiment_values) > 1 else 1.0,
            "count": len(sentiment_values),
            "min": min(sentiment_values),
            "max": max(sentiment_values)
        }
