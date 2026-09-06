"""
Anomaly Detection Engine

Implements statistical anomaly detection algorithms for:
- Price and volume anomalies
- Sentiment anomalies  
- Cross-asset correlation anomalies
- Time series pattern anomalies
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, date
from dataclasses import dataclass
from statistics import mean, stdev
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from app.models.price import Price
from app.models.article import Article
from app.models.ticker_features_daily import TickerFeaturesDaily
from app.models.stock import Stock

logger = logging.getLogger(__name__)


@dataclass
class AnomalyResult:
    """Result of anomaly detection"""
    ticker: str
    anomaly_type: str
    severity: float  # 0-1 scale
    z_score: float
    current_value: float
    expected_value: float
    threshold: float
    confidence: float
    detected_at: datetime
    metadata: Dict[str, Any]


class StatisticalAnomalyDetector:
    """
    Statistical anomaly detection using z-scores and rolling statistics
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.default_lookback_days = 30
        self.default_z_threshold = 2.5
    
    def detect_price_anomalies(
        self, 
        ticker: str, 
        lookback_days: int = None, 
        z_threshold: float = None
    ) -> List[AnomalyResult]:
        """
        Detect price and volume anomalies for a ticker
        """
        lookback_days = lookback_days or self.default_lookback_days
        z_threshold = z_threshold or self.default_z_threshold
        
        anomalies = []
        
        # Get recent price data
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=lookback_days)
        
        prices = self.db.query(Price).filter(
            and_(
                Price.symbol == ticker.upper(),
                func.date(Price.timestamp) >= start_date,
                func.date(Price.timestamp) <= end_date
            )
        ).order_by(Price.timestamp.desc()).all()
        
        if len(prices) < 10:  # Need minimum data points
            return anomalies
        
        # Get latest price data
        latest_price = prices[0]
        historical_prices = prices[1:]
        
        # Calculate price change anomalies
        price_changes = []
        volumes = []
        
        for i in range(len(historical_prices) - 1):
            current = historical_prices[i]
            previous = historical_prices[i + 1]
            
            if current.close and previous.close:
                change = (current.close - previous.close) / previous.close
                price_changes.append(change)
            
            if current.volume:
                volumes.append(float(current.volume))
        
        # Detect price change anomalies
        if price_changes and latest_price.close and len(historical_prices) > 0:
            latest_change = (latest_price.close - historical_prices[0].close) / historical_prices[0].close
            
            if len(price_changes) > 5:
                mean_change = mean(price_changes)
                std_change = stdev(price_changes) if len(price_changes) > 1 else 0.01
                
                z_score = (latest_change - mean_change) / std_change if std_change > 0 else 0
                
                if abs(z_score) > z_threshold:
                    anomalies.append(AnomalyResult(
                        ticker=ticker,
                        anomaly_type="price_change",
                        severity=min(abs(z_score) / 5.0, 1.0),
                        z_score=z_score,
                        current_value=latest_change,
                        expected_value=mean_change,
                        threshold=z_threshold,
                        confidence=min(len(price_changes) / 20.0, 1.0),
                        detected_at=datetime.utcnow(),
                        metadata={
                            "price_change_pct": round(latest_change * 100, 2),
                            "historical_mean_pct": round(mean_change * 100, 2),
                            "historical_std_pct": round(std_change * 100, 2),
                            "lookback_days": lookback_days
                        }
                    ))
        
        # Detect volume anomalies
        if volumes and latest_price.volume:
            if len(volumes) > 5:
                mean_volume = mean(volumes)
                std_volume = stdev(volumes) if len(volumes) > 1 else mean_volume * 0.1
                
                volume_z = (float(latest_price.volume) - mean_volume) / std_volume if std_volume > 0 else 0
                
                if abs(volume_z) > z_threshold:
                    anomalies.append(AnomalyResult(
                        ticker=ticker,
                        anomaly_type="volume_spike",
                        severity=min(abs(volume_z) / 5.0, 1.0),
                        z_score=volume_z,
                        current_value=float(latest_price.volume),
                        expected_value=mean_volume,
                        threshold=z_threshold,
                        confidence=min(len(volumes) / 20.0, 1.0),
                        detected_at=datetime.utcnow(),
                        metadata={
                            "volume_multiple": round(float(latest_price.volume) / mean_volume, 2),
                            "historical_mean_volume": round(mean_volume),
                            "lookback_days": lookback_days
                        }
                    ))
        
        return anomalies
    
    def detect_sentiment_anomalies(
        self, 
        ticker: str, 
        lookback_days: int = None,
        z_threshold: float = None
    ) -> List[AnomalyResult]:
        """
        Detect sentiment anomalies based on article sentiment patterns
        """
        lookback_days = lookback_days or self.default_lookback_days
        z_threshold = z_threshold or self.default_z_threshold
        
        anomalies = []
        
        # Get recent articles
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)
        
        articles = self.db.query(Article).filter(
            and_(
                Article.tickers.contains([ticker.upper()]),
                Article.published_at >= start_date,
                Article.published_at <= end_date,
                Article.sentiment.isnot(None)
            )
        ).order_by(Article.published_at.desc()).all()
        
        if len(articles) < 5:
            return anomalies
        
        # Group articles by day and calculate daily sentiment
        daily_sentiments = {}
        for article in articles:
            day = article.published_at.date()
            if day not in daily_sentiments:
                daily_sentiments[day] = []
            daily_sentiments[day].append(article.sentiment)
        
        # Calculate daily average sentiments
        daily_averages = {}
        for day, sentiments in daily_sentiments.items():
            daily_averages[day] = mean(sentiments)
        
        if len(daily_averages) < 3:
            return anomalies
        
        # Get recent sentiment (last 3 days)
        recent_days = sorted(daily_averages.keys(), reverse=True)[:3]
        recent_sentiment = mean([daily_averages[day] for day in recent_days])
        
        # Calculate historical baseline (excluding recent days)
        historical_days = [day for day in daily_averages.keys() if day not in recent_days]
        if len(historical_days) < 3:
            return anomalies
        
        historical_sentiments = [daily_averages[day] for day in historical_days]
        mean_sentiment = mean(historical_sentiments)
        std_sentiment = stdev(historical_sentiments) if len(historical_sentiments) > 1 else 0.1
        
        # Calculate z-score
        sentiment_z = (recent_sentiment - mean_sentiment) / std_sentiment if std_sentiment > 0 else 0
        
        if abs(sentiment_z) > z_threshold:
            anomalies.append(AnomalyResult(
                ticker=ticker,
                anomaly_type="sentiment_anomaly",
                severity=min(abs(sentiment_z) / 5.0, 1.0),
                z_score=sentiment_z,
                current_value=recent_sentiment,
                expected_value=mean_sentiment,
                threshold=z_threshold,
                confidence=min(len(articles) / 30.0, 1.0),
                detected_at=datetime.utcnow(),
                metadata={
                    "recent_sentiment": round(recent_sentiment, 3),
                    "historical_mean": round(mean_sentiment, 3),
                    "article_count": len(articles),
                    "days_analyzed": len(daily_averages),
                    "direction": "positive" if sentiment_z > 0 else "negative"
                }
            ))
        
        return anomalies
    
    def detect_feature_anomalies(
        self, 
        ticker: str, 
        feature_name: str,
        lookback_days: int = None,
        z_threshold: float = None
    ) -> List[AnomalyResult]:
        """
        Detect anomalies in specific feature values
        """
        lookback_days = lookback_days or self.default_lookback_days
        z_threshold = z_threshold or self.default_z_threshold
        
        # Get recent feature data
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        
        features = self.db.query(TickerFeaturesDaily).filter(
            and_(
                TickerFeaturesDaily.ticker == ticker.upper(),
                TickerFeaturesDaily.date >= start_date,
                TickerFeaturesDaily.date <= end_date
            )
        ).order_by(TickerFeaturesDaily.date.desc()).all()
        
        if len(features) < 5:
            return []
        
        # Extract feature values
        feature_values = []
        latest_value = None
        
        for f in features:
            value = getattr(f, feature_name, None)
            if value is not None:
                if latest_value is None:  # First (most recent) value
                    latest_value = float(value)
                else:
                    feature_values.append(float(value))
        
        if latest_value is None or len(feature_values) < 3:
            return []
        
        # Calculate statistics
        mean_value = mean(feature_values)
        std_value = stdev(feature_values) if len(feature_values) > 1 else abs(mean_value) * 0.1
        
        # Calculate z-score
        z_score = (latest_value - mean_value) / std_value if std_value > 0 else 0
        
        if abs(z_score) > z_threshold:
            return [AnomalyResult(
                ticker=ticker,
                anomaly_type=f"{feature_name}_anomaly",
                severity=min(abs(z_score) / 5.0, 1.0),
                z_score=z_score,
                current_value=latest_value,
                expected_value=mean_value,
                threshold=z_threshold,
                confidence=min(len(feature_values) / 15.0, 1.0),
                detected_at=datetime.utcnow(),
                metadata={
                    "feature_name": feature_name,
                    "historical_mean": round(mean_value, 4),
                    "historical_std": round(std_value, 4),
                    "data_points": len(feature_values),
                    "direction": "above" if z_score > 0 else "below"
                }
            )]
        
        return []


class CrossAssetAnomalyDetector:
    """
    Detect anomalies in cross-asset correlations and market-wide patterns
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_correlation_anomalies(
        self, 
        ticker_pairs: List[Tuple[str, str]] = None,
        lookback_days: int = 30,
        correlation_threshold: float = 0.8
    ) -> List[AnomalyResult]:
        """
        Detect unusual correlation patterns between asset pairs
        """
        if ticker_pairs is None:
            # Default pairs for major stocks
            ticker_pairs = [
                ("AAPL", "MSFT"), ("GOOGL", "META"), ("TSLA", "NVDA"),
                ("JPM", "BAC"), ("XOM", "CVX"), ("JNJ", "PFE")
            ]
        
        anomalies = []
        
        for ticker1, ticker2 in ticker_pairs:
            try:
                correlation_anomaly = self._analyze_pair_correlation(
                    ticker1, ticker2, lookback_days, correlation_threshold
                )
                if correlation_anomaly:
                    anomalies.append(correlation_anomaly)
            except Exception as e:
                logger.error(f"Error analyzing correlation {ticker1}-{ticker2}: {e}")
                continue
        
        return anomalies
    
    def _analyze_pair_correlation(
        self, 
        ticker1: str, 
        ticker2: str, 
        lookback_days: int,
        threshold: float
    ) -> Optional[AnomalyResult]:
        """
        Analyze correlation between two tickers
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Get feature data for both tickers
        features1 = self.db.query(TickerFeaturesDaily).filter(
            and_(
                TickerFeaturesDaily.ticker == ticker1.upper(),
                TickerFeaturesDaily.date >= start_date,
                TickerFeaturesDaily.date <= end_date,
                TickerFeaturesDaily.ret_1d.isnot(None)
            )
        ).order_by(TickerFeaturesDaily.date.desc()).all()
        
        features2 = self.db.query(TickerFeaturesDaily).filter(
            and_(
                TickerFeaturesDaily.ticker == ticker2.upper(),
                TickerFeaturesDaily.date >= start_date,
                TickerFeaturesDaily.date <= end_date,
                TickerFeaturesDaily.ret_1d.isnot(None)
            )
        ).order_by(TickerFeaturesDaily.date.desc()).all()
        
        if len(features1) < 10 or len(features2) < 10:
            return None
        
        # Align dates and extract returns
        returns1_dict = {f.date: float(f.ret_1d) for f in features1 if f.ret_1d}
        returns2_dict = {f.date: float(f.ret_1d) for f in features2 if f.ret_1d}
        
        # Find common dates
        common_dates = set(returns1_dict.keys()) & set(returns2_dict.keys())
        if len(common_dates) < 10:
            return None
        
        # Extract aligned returns
        aligned_returns1 = [returns1_dict[date] for date in sorted(common_dates)]
        aligned_returns2 = [returns2_dict[date] for date in sorted(common_dates)]
        
        # Calculate correlation
        correlation = np.corrcoef(aligned_returns1, aligned_returns2)[0, 1]
        
        if np.isnan(correlation):
            return None
        
        # Get historical correlation (longer period)
        historical_start = start_date - timedelta(days=lookback_days * 2)
        
        # Get historical data for baseline
        hist_features1 = self.db.query(TickerFeaturesDaily).filter(
            and_(
                TickerFeaturesDaily.ticker == ticker1.upper(),
                TickerFeaturesDaily.date >= historical_start,
                TickerFeaturesDaily.date < start_date,
                TickerFeaturesDaily.ret_1d.isnot(None)
            )
        ).all()
        
        hist_features2 = self.db.query(TickerFeaturesDaily).filter(
            and_(
                TickerFeaturesDaily.ticker == ticker2.upper(),
                TickerFeaturesDaily.date >= historical_start,
                TickerFeaturesDaily.date < start_date,
                TickerFeaturesDaily.ret_1d.isnot(None)
            )
        ).all()
        
        if len(hist_features1) < 10 or len(hist_features2) < 10:
            # Use current correlation as baseline if no historical data
            historical_correlation = 0.0
        else:
            hist_returns1_dict = {f.date: float(f.ret_1d) for f in hist_features1 if f.ret_1d}
            hist_returns2_dict = {f.date: float(f.ret_1d) for f in hist_features2 if f.ret_1d}
            
            hist_common_dates = set(hist_returns1_dict.keys()) & set(hist_returns2_dict.keys())
            if len(hist_common_dates) >= 10:
                hist_aligned1 = [hist_returns1_dict[date] for date in sorted(hist_common_dates)]
                hist_aligned2 = [hist_returns2_dict[date] for date in sorted(hist_common_dates)]
                historical_correlation = np.corrcoef(hist_aligned1, hist_aligned2)[0, 1]
                
                if np.isnan(historical_correlation):
                    historical_correlation = 0.0
            else:
                historical_correlation = 0.0
        
        # Check for correlation breakdown
        correlation_change = abs(correlation - historical_correlation)
        
        if correlation_change > threshold:
            return AnomalyResult(
                ticker=f"{ticker1}-{ticker2}",
                anomaly_type="correlation_breakdown",
                severity=min(correlation_change, 1.0),
                z_score=correlation_change / 0.3,  # Normalize to z-score equivalent
                current_value=correlation,
                expected_value=historical_correlation,
                threshold=threshold,
                confidence=min(len(common_dates) / 20.0, 1.0),
                detected_at=datetime.utcnow(),
                metadata={
                    "ticker1": ticker1,
                    "ticker2": ticker2,
                    "current_correlation": round(correlation, 3),
                    "historical_correlation": round(historical_correlation, 3),
                    "correlation_change": round(correlation_change, 3),
                    "data_points": len(common_dates)
                }
            )
        
        return None
    
    def detect_market_wide_anomalies(
        self, 
        lookback_days: int = 30
    ) -> List[AnomalyResult]:
        """
        Detect market-wide anomalies affecting multiple stocks
        """
        anomalies = []
        
        # Get major stocks for market analysis
        major_stocks = self.db.query(Stock.symbol).limit(20).all()
        tickers = [stock.symbol for stock in major_stocks]
        
        if len(tickers) < 5:
            return anomalies
        
        # Analyze market-wide sentiment
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Get sentiment distribution across major stocks
        sentiment_data = []
        
        for ticker in tickers:
            ticker_articles = self.db.query(Article).filter(
                and_(
                    Article.tickers.contains([ticker]),
                    Article.published_at >= start_date,
                    Article.sentiment.isnot(None)
                )
            ).all()
            
            if ticker_articles:
                avg_sentiment = mean([a.sentiment for a in ticker_articles])
                sentiment_data.append((ticker, avg_sentiment, len(ticker_articles)))
        
        if len(sentiment_data) < 5:
            return anomalies
        
        # Calculate market sentiment metrics
        market_sentiments = [data[1] for data in sentiment_data]
        market_mean = mean(market_sentiments)
        market_std = stdev(market_sentiments) if len(market_sentiments) > 1 else 0.1
        
        # Detect extreme market sentiment
        if market_std < 0.05:  # Very low volatility in sentiment
            anomalies.append(AnomalyResult(
                ticker="MARKET",
                anomaly_type="sentiment_consensus",
                severity=0.7,
                z_score=0,
                current_value=market_mean,
                expected_value=0.5,
                threshold=0.05,
                confidence=0.8,
                detected_at=datetime.utcnow(),
                metadata={
                    "market_sentiment": round(market_mean, 3),
                    "sentiment_std": round(market_std, 3),
                    "stocks_analyzed": len(sentiment_data),
                    "consensus_type": "bullish" if market_mean > 0.6 else "bearish" if market_mean < 0.4 else "neutral"
                }
            ))
        
        # Detect unusual sentiment extremes
        extreme_count = sum(1 for sentiment in market_sentiments if sentiment > 0.8 or sentiment < 0.2)
        extreme_ratio = extreme_count / len(market_sentiments)
        
        if extreme_ratio > 0.3:  # 30% of stocks have extreme sentiment
            anomalies.append(AnomalyResult(
                ticker="MARKET",
                anomaly_type="sentiment_extremes",
                severity=extreme_ratio,
                z_score=extreme_ratio / 0.1,
                current_value=extreme_ratio,
                expected_value=0.1,
                threshold=0.3,
                confidence=0.8,
                detected_at=datetime.utcnow(),
                metadata={
                    "extreme_ratio": round(extreme_ratio, 3),
                    "extreme_stocks": extreme_count,
                    "total_stocks": len(sentiment_data),
                    "market_sentiment": round(market_mean, 3)
                }
            ))
        
        return anomalies


class TimeSeriesAnomalyDetector:
    """
    Detect anomalies in time series patterns using statistical methods
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_pattern_breaks(
        self, 
        ticker: str, 
        lookback_days: int = 60
    ) -> List[AnomalyResult]:
        """
        Detect breaks in established patterns (trends, cycles)
        """
        anomalies = []
        
        # Get price history
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=lookback_days)
        
        prices = self.db.query(Price).filter(
            and_(
                Price.symbol == ticker.upper(),
                func.date(Price.timestamp) >= start_date,
                func.date(Price.timestamp) <= end_date,
                Price.close.isnot(None)
            )
        ).order_by(Price.timestamp.asc()).all()
        
        if len(prices) < 20:
            return anomalies
        
        # Extract closing prices
        closes = [float(p.close) for p in prices]
        dates = [p.timestamp.date() for p in prices]
        
        # Simple trend detection using linear regression
        try:
            # Calculate trend over first 80% of data
            split_point = int(len(closes) * 0.8)
            trend_data = closes[:split_point]
            recent_data = closes[split_point:]
            
            if len(trend_data) < 10 or len(recent_data) < 5:
                return anomalies
            
            # Calculate trend slope
            x_trend = np.arange(len(trend_data))
            trend_slope = np.polyfit(x_trend, trend_data, 1)[0]
            
            # Calculate recent slope
            x_recent = np.arange(len(recent_data))
            recent_slope = np.polyfit(x_recent, recent_data, 1)[0]
            
            # Detect trend reversal
            if abs(trend_slope) > 0.1:  # Significant trend exists
                slope_change = abs(recent_slope - trend_slope) / abs(trend_slope)
                
                if slope_change > 2.0:  # 200% change in slope
                    anomalies.append(AnomalyResult(
                        ticker=ticker,
                        anomaly_type="trend_reversal",
                        severity=min(slope_change / 5.0, 1.0),
                        z_score=slope_change,
                        current_value=recent_slope,
                        expected_value=trend_slope,
                        threshold=2.0,
                        confidence=0.7,
                        detected_at=datetime.utcnow(),
                        metadata={
                            "trend_slope": round(trend_slope, 4),
                            "recent_slope": round(recent_slope, 4),
                            "slope_change_ratio": round(slope_change, 2),
                            "trend_direction": "upward" if trend_slope > 0 else "downward",
                            "reversal_direction": "upward" if recent_slope > 0 else "downward"
                        }
                    ))
            
        except Exception as e:
            logger.error(f"Error in trend analysis for {ticker}: {e}")
        
        return anomalies
    
    def detect_volatility_anomalies(
        self, 
        ticker: str, 
        lookback_days: int = 30,
        volatility_threshold: float = 2.0
    ) -> List[AnomalyResult]:
        """
        Detect unusual volatility patterns
        """
        # Get recent returns from features
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        
        features = self.db.query(TickerFeaturesDaily).filter(
            and_(
                TickerFeaturesDaily.ticker == ticker.upper(),
                TickerFeaturesDaily.date >= start_date,
                TickerFeaturesDaily.ret_1d.isnot(None)
            )
        ).order_by(TickerFeaturesDaily.date.desc()).all()
        
        if len(features) < 15:
            return []
        
        # Calculate rolling volatility
        returns = [float(f.ret_1d) for f in features]
        
        # Recent volatility (last 5 days)
        recent_returns = returns[:5]
        recent_volatility = stdev(recent_returns) if len(recent_returns) > 1 else 0
        
        # Historical volatility (remaining data)
        historical_returns = returns[5:]
        historical_volatility = stdev(historical_returns) if len(historical_returns) > 1 else 0.01
        
        # Calculate volatility ratio
        if historical_volatility > 0:
            volatility_ratio = recent_volatility / historical_volatility
            
            if volatility_ratio > volatility_threshold:
                return [AnomalyResult(
                    ticker=ticker,
                    anomaly_type="volatility_spike",
                    severity=min(volatility_ratio / 5.0, 1.0),
                    z_score=volatility_ratio,
                    current_value=recent_volatility,
                    expected_value=historical_volatility,
                    threshold=volatility_threshold,
                    confidence=min(len(features) / 20.0, 1.0),
                    detected_at=datetime.utcnow(),
                    metadata={
                        "recent_volatility": round(recent_volatility, 4),
                        "historical_volatility": round(historical_volatility, 4),
                        "volatility_ratio": round(volatility_ratio, 2),
                        "data_points": len(features)
                    }
                )]
        
        return []


# NOTE: an empty duplicate `class TimeSeriesAnomalyDetector` used to live here
# and SHADOWED the real implementation above (Python keeps the last definition),
# deleting detect_pattern_breaks/detect_volatility_anomalies from existence:
# every /anomalies/patterns call 500'd. Do not redefine the class below.


class AnomalyDetectionOrchestrator:
    """
    Main orchestrator that runs all anomaly detection algorithms
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.statistical_detector = StatisticalAnomalyDetector(db)
        self.cross_asset_detector = CrossAssetAnomalyDetector(db)
        self.time_series_detector = TimeSeriesAnomalyDetector(db)
    
    def detect_all_anomalies(
        self, 
        ticker: str = None, 
        include_market_wide: bool = True
    ) -> List[AnomalyResult]:
        """
        Run all anomaly detection algorithms
        """
        all_anomalies = []
        
        if ticker:
            # Single ticker analysis
            tickers_to_analyze = [ticker.upper()]
        else:
            # Get active stocks for analysis
            stocks = self.db.query(Stock.symbol).limit(50).all()
            tickers_to_analyze = [stock.symbol for stock in stocks]
        
        # Run statistical anomaly detection for each ticker
        for t in tickers_to_analyze:
            try:
                # Price and volume anomalies
                price_anomalies = self.statistical_detector.detect_price_anomalies(t)
                all_anomalies.extend(price_anomalies)
                
                # Sentiment anomalies
                sentiment_anomalies = self.statistical_detector.detect_sentiment_anomalies(t)
                all_anomalies.extend(sentiment_anomalies)
                
                # Feature anomalies (key features)
                key_features = ['momentum_14d', 'wsb_sentiment_7d', 'retail_buzz_score', 'meme_stock_indicator']
                for feature in key_features:
                    feature_anomalies = self.statistical_detector.detect_feature_anomalies(t, feature)
                    all_anomalies.extend(feature_anomalies)
                
                # Time series pattern anomalies
                pattern_anomalies = self.time_series_detector.detect_pattern_breaks(t)
                all_anomalies.extend(pattern_anomalies)
                
                # Volatility anomalies
                volatility_anomalies = self.time_series_detector.detect_volatility_anomalies(t)
                all_anomalies.extend(volatility_anomalies)
                
            except Exception as e:
                logger.error(f"Error detecting anomalies for {t}: {e}")
                continue
        
        # Market-wide anomaly detection
        if include_market_wide:
            try:
                correlation_anomalies = self.cross_asset_detector.detect_correlation_anomalies()
                all_anomalies.extend(correlation_anomalies)
                
                market_anomalies = self.statistical_detector.detect_market_wide_anomalies()
                all_anomalies.extend(market_anomalies)
                
            except Exception as e:
                logger.error(f"Error detecting market-wide anomalies: {e}")
        
        # Sort by severity (highest first)
        all_anomalies.sort(key=lambda x: x.severity, reverse=True)
        
        return all_anomalies
    
    def get_anomaly_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of anomalies detected in the last N hours
        """
        # For now, this is a placeholder since we don't store anomaly history
        # In production, you'd want to store anomalies in a separate table
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return {
            "summary": "Anomaly detection summary",
            "period_hours": hours,
            "note": "Real-time anomaly detection - results not persisted yet",
            "generated_at": datetime.utcnow().isoformat()
        }
