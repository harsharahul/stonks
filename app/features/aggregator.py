"""
Feature aggregator for combining all deterministic features
"""

from typing import Dict, List, Optional
from datetime import date, datetime
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.models.ticker_features_daily import TickerFeaturesDaily
from .sentiment import SentimentFeatures, SentimentMetrics
from .momentum import MomentumFeatures, MomentumMetrics
from .novelty import NoveltyFeatures, NoveltyMetrics
from .retail_sentiment import RetailSentimentFeatures, RetailSentimentMetrics


@dataclass
class AggregatedFeatures:
    """Combined features for a ticker on a specific date"""
    ticker: str
    date: date
    
    # Sentiment features
    sent_mean_3d: Optional[float] = None
    sent_mean_7d: Optional[float] = None
    sent_mean_10d: Optional[float] = None
    sent_shock: Optional[float] = None
    sent_volume_weighted: Optional[float] = None
    
    # Momentum features
    ret_1d: Optional[float] = None
    ret_5d: Optional[float] = None
    ret_20d: Optional[float] = None
    vol_z: Optional[float] = None
    momentum_14d: Optional[float] = None
    
    # Context features
    earnings_d: Optional[int] = None
    conflict_score: Optional[float] = None
    novelty_mean_3d: Optional[float] = None
    
    # Retail sentiment features (WSB)
    wsb_sentiment_3d: Optional[float] = None
    wsb_sentiment_7d: Optional[float] = None
    wsb_mention_count_7d: int = 0
    wsb_engagement_score: Optional[float] = None
    retail_buzz_score: Optional[float] = None
    meme_stock_indicator: Optional[float] = None
    
    # Metadata
    article_count_7d: int = 0
    top_doc_ids: List[str] = None
    feature_version: str = "v1.0.0"
    
    def __post_init__(self):
        if self.top_doc_ids is None:
            self.top_doc_ids = []


class FeatureAggregator:
    """Orchestrates feature calculation across all calculators"""
    
    def __init__(self, db: Session):
        self.db = db
        self.feature_version = "v1.0.0"
    
    def calculate_features_for_ticker(
        self, 
        ticker: str, 
        target_date: date
    ) -> AggregatedFeatures:
        """
        Calculate all features for a single ticker
        
        Args:
            ticker: Stock ticker symbol
            target_date: Date to calculate features for
            
        Returns:
            AggregatedFeatures with all calculated metrics
        """
        
        # Calculate individual feature groups
        sentiment = SentimentFeatures.calculate_for_ticker(
            self.db, ticker, target_date
        )
        
        momentum = MomentumFeatures.calculate_for_ticker(
            self.db, ticker, target_date
        )
        
        novelty = NoveltyFeatures.calculate_for_ticker(
            self.db, ticker, target_date
        )
        
        # Calculate retail sentiment features (WSB)
        retail_sentiment = RetailSentimentFeatures.calculate_for_ticker(
            self.db, ticker, target_date
        )
        
        # Calculate conflict score (variance in sentiment across recent articles)
        conflict_score = self._calculate_conflict_score(ticker, target_date)
        
        # TODO: Calculate earnings days (integrate with earnings calendar)
        earnings_d = None
        
        # Get top document IDs for traceability
        top_doc_ids = self._get_top_documents(ticker, target_date)
        
        # Combine into aggregated features
        features = AggregatedFeatures(
            ticker=ticker,
            date=target_date,
            
            # Sentiment
            sent_mean_3d=sentiment.mean_3d,
            sent_mean_7d=sentiment.mean_7d,
            sent_mean_10d=sentiment.mean_10d,
            sent_shock=sentiment.shock,
            sent_volume_weighted=sentiment.volume_weighted,
            
            # Momentum
            ret_1d=momentum.ret_1d,
            ret_5d=momentum.ret_5d,
            ret_20d=momentum.ret_20d,
            vol_z=momentum.vol_z,
            momentum_14d=momentum.momentum_14d,
            
            # Context
            earnings_d=earnings_d,
            conflict_score=conflict_score,
            novelty_mean_3d=novelty.novelty_mean_3d,
            
            # Retail sentiment (WSB)
            wsb_sentiment_3d=retail_sentiment.wsb_sentiment_3d,
            wsb_sentiment_7d=retail_sentiment.wsb_sentiment_7d,
            wsb_mention_count_7d=retail_sentiment.wsb_mention_count_7d,
            wsb_engagement_score=retail_sentiment.wsb_engagement_score,
            retail_buzz_score=retail_sentiment.retail_buzz_score,
            meme_stock_indicator=retail_sentiment.meme_stock_indicator,
            
            # Metadata
            article_count_7d=sentiment.article_count,
            top_doc_ids=top_doc_ids,
            feature_version=self.feature_version
        )
        
        return features
    
    def calculate_bulk_features(
        self, 
        tickers: List[str], 
        target_date: date
    ) -> Dict[str, AggregatedFeatures]:
        """
        Calculate features for multiple tickers efficiently
        
        Args:
            tickers: List of ticker symbols
            target_date: Date to calculate features for
            
        Returns:
            Dictionary mapping ticker -> AggregatedFeatures
        """
        results = {}
        
        # For now, calculate individually
        # TODO: Optimize with bulk calculations
        for ticker in tickers:
            try:
                features = self.calculate_features_for_ticker(ticker, target_date)
                results[ticker] = features
            except Exception as e:
                print(f"Error calculating features for {ticker}: {e}")
                # Continue with other tickers
                continue
        
        return results
    
    def store_features(self, features: AggregatedFeatures) -> TickerFeaturesDaily:
        """
        Store aggregated features in the feature store
        
        Args:
            features: AggregatedFeatures to store
            
        Returns:
            Created TickerFeaturesDaily record
        """
        
        # Check if features already exist for this ticker/date/version
        existing = self.db.query(TickerFeaturesDaily).filter(
            TickerFeaturesDaily.ticker == features.ticker,
            TickerFeaturesDaily.date == features.date,
            TickerFeaturesDaily.feature_version == features.feature_version
        ).first()
        
        if existing:
            # Update existing record
            record = existing
        else:
            # Create new record
            record = TickerFeaturesDaily(
                ticker=features.ticker,
                date=features.date,
                feature_version=features.feature_version
            )
            self.db.add(record)
        
        # Update all fields
        record.sent_mean_3d = features.sent_mean_3d
        record.sent_mean_7d = features.sent_mean_7d
        record.sent_mean_10d = features.sent_mean_10d
        record.sent_shock = features.sent_shock
        record.sent_volume_weighted = features.sent_volume_weighted
        
        record.ret_1d = features.ret_1d
        record.ret_5d = features.ret_5d
        record.ret_20d = features.ret_20d
        record.vol_z = features.vol_z
        record.momentum_14d = features.momentum_14d
        
        record.earnings_d = features.earnings_d
        record.conflict_score = features.conflict_score
        record.novelty_mean_3d = features.novelty_mean_3d
        
        record.article_count_7d = features.article_count_7d
        record.top_doc_ids = features.top_doc_ids
        record.model_version = f"deterministic_{features.feature_version}"
        
        self.db.flush()
        return record
    
    def calculate_and_store_daily_features(
        self, 
        target_date: Optional[date] = None,
        tickers: Optional[List[str]] = None
    ) -> Dict[str, TickerFeaturesDaily]:
        """
        Calculate and store features for all active tickers on a given date
        
        Args:
            target_date: Date to calculate for (defaults to today)
            tickers: Specific tickers to process (defaults to all active)
            
        Returns:
            Dictionary mapping ticker -> stored TickerFeaturesDaily record
        """
        if target_date is None:
            target_date = date.today()
        
        if tickers is None:
            # Get all active tickers
            active_stocks = self.db.query(Stock).filter(Stock.is_active == True).all()
            tickers = [stock.symbol for stock in active_stocks]
        
        print(f"Calculating features for {len(tickers)} tickers on {target_date}")
        
        # Calculate features
        bulk_features = self.calculate_bulk_features(tickers, target_date)
        
        # Store features
        stored_records = {}
        for ticker, features in bulk_features.items():
            try:
                record = self.store_features(features)
                stored_records[ticker] = record
                print(f"✅ Stored features for {ticker}")
            except Exception as e:
                print(f"❌ Error storing features for {ticker}: {e}")
        
        # Commit all changes
        self.db.commit()
        
        print(f"🎉 Completed feature calculation for {len(stored_records)}/{len(tickers)} tickers")
        return stored_records
    
    def _calculate_conflict_score(self, ticker: str, target_date: date) -> Optional[float]:
        """Calculate conflict score (sentiment variance across sources)"""
        from datetime import timedelta
        from statistics import stdev
        from app.models.article import Article
        from app.models.doc_entity import DocEntity
        
        recent_7d = target_date - timedelta(days=7)
        
        # Get recent articles with sentiment from different sources
        articles = self.db.query(Article).join(DocEntity).filter(
            DocEntity.ticker == ticker,
            Article.sentiment.isnot(None),
            Article.published_at >= recent_7d,
            Article.published_at <= target_date
        ).all()
        
        if len(articles) < 2:
            return None
        
        # Group by source and calculate average sentiment per source
        source_sentiments = {}
        for article in articles:
            if article.url:
                # Extract domain as source
                source = article.url.split('/')[2] if '/' in article.url else article.url
                if source not in source_sentiments:
                    source_sentiments[source] = []
                source_sentiments[source].append(float(article.sentiment))
        
        # Calculate average sentiment per source
        source_averages = []
        for source, sentiments in source_sentiments.items():
            if sentiments:
                avg_sentiment = sum(sentiments) / len(sentiments)
                source_averages.append(avg_sentiment)
        
        # Return standard deviation of source averages (conflict score)
        if len(source_averages) > 1:
            return stdev(source_averages)
        
        return 0.0  # No conflict if only one source
    
    def _get_top_documents(self, ticker: str, target_date: date, limit: int = 5) -> List[str]:
        """Get top document IDs for traceability"""
        from datetime import timedelta
        from app.models.article import Article
        from app.models.doc_entity import DocEntity
        
        recent_7d = target_date - timedelta(days=7)
        
        # Get recent articles, prioritize by novelty/sentiment
        articles = self.db.query(Article).join(DocEntity).filter(
            DocEntity.ticker == ticker,
            Article.published_at >= recent_7d,
            Article.published_at <= target_date
        ).order_by(
            Article.published_at.desc()  # Most recent first
        ).limit(limit).all()
        
        return [article.id for article in articles]
