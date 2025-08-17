"""
Momentum and market feature calculators for deterministic analytics
"""

from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from statistics import mean, stdev
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.price import Price
from app.models.stock import Stock


@dataclass
class MomentumMetrics:
    """Container for momentum and market metrics"""
    ret_1d: Optional[float] = None
    ret_5d: Optional[float] = None
    ret_20d: Optional[float] = None
    momentum_14d: Optional[float] = None
    vol_z: Optional[float] = None  # volume z-score
    volatility_20d: Optional[float] = None
    price_trend_days: int = 0  # consecutive days of price increase


class MomentumFeatures:
    """Market momentum and volatility feature calculations"""
    
    @staticmethod
    def calculate_returns(prices: List[Tuple[date, float]]) -> Dict[str, Optional[float]]:
        """
        Calculate returns over different periods
        
        Args:
            prices: List of (date, close_price) tuples, sorted by date DESC
            
        Returns:
            Dictionary with return metrics
        """
        if len(prices) < 2:
            return {"ret_1d": None, "ret_5d": None, "ret_20d": None, "momentum_14d": None}
        
        # Convert to list sorted by date ASC for easier indexing
        prices_asc = sorted(prices, key=lambda x: x[0])
        closes = [p[1] for p in prices_asc]
        
        results = {}
        
        # 1-day return
        if len(closes) >= 2:
            results["ret_1d"] = (closes[-1] - closes[-2]) / closes[-2]
        else:
            results["ret_1d"] = None
        
        # 5-day return
        if len(closes) >= 6:
            results["ret_5d"] = (closes[-1] - closes[-6]) / closes[-6]
        else:
            results["ret_5d"] = None
        
        # 20-day return
        if len(closes) >= 21:
            results["ret_20d"] = (closes[-1] - closes[-21]) / closes[-21]
        else:
            results["ret_20d"] = None
        
        # 14-day momentum (average daily return)
        if len(closes) >= 15:
            daily_returns = []
            for i in range(len(closes) - 14, len(closes)):
                if i > 0:
                    daily_ret = (closes[i] - closes[i-1]) / closes[i-1]
                    daily_returns.append(daily_ret)
            
            if daily_returns:
                results["momentum_14d"] = mean(daily_returns)
            else:
                results["momentum_14d"] = None
        else:
            results["momentum_14d"] = None
        
        return results
    
    @staticmethod
    def calculate_volume_zscore(
        volumes: List[Tuple[date, float]], 
        window: int = 60
    ) -> Optional[float]:
        """
        Calculate volume z-score vs rolling window
        
        Args:
            volumes: List of (date, volume) tuples, sorted by date DESC
            window: Rolling window for z-score calculation
            
        Returns:
            Volume z-score or None if insufficient data
        """
        if len(volumes) < window + 1:
            return None
        
        # Get current volume and historical window
        current_volume = volumes[0][1]  # Most recent
        historical_volumes = [v[1] for v in volumes[1:window+1]]
        
        if len(historical_volumes) < 2:
            return None
        
        hist_mean = mean(historical_volumes)
        hist_std = stdev(historical_volumes)
        
        if hist_std == 0:
            return 0.0
        
        return (current_volume - hist_mean) / hist_std
    
    @staticmethod
    def calculate_volatility(prices: List[Tuple[date, float]], days: int = 20) -> Optional[float]:
        """
        Calculate price volatility (standard deviation of daily returns)
        
        Args:
            prices: List of (date, close_price) tuples, sorted by date DESC
            days: Number of days to calculate volatility over
            
        Returns:
            Annualized volatility or None if insufficient data
        """
        if len(prices) < days + 1:
            return None
        
        # Calculate daily returns
        prices_asc = sorted(prices[:days+1], key=lambda x: x[0])
        closes = [p[1] for p in prices_asc]
        
        daily_returns = []
        for i in range(1, len(closes)):
            ret = (closes[i] - closes[i-1]) / closes[i-1]
            daily_returns.append(ret)
        
        if len(daily_returns) < 2:
            return None
        
        # Annualized volatility (assume 252 trading days)
        vol_daily = stdev(daily_returns)
        return vol_daily * (252 ** 0.5)
    
    @staticmethod
    def count_trend_days(prices: List[Tuple[date, float]]) -> int:
        """
        Count consecutive days of price increases from most recent
        
        Args:
            prices: List of (date, close_price) tuples, sorted by date DESC
            
        Returns:
            Number of consecutive up days
        """
        if len(prices) < 2:
            return 0
        
        # Sort by date ascending for easier logic
        prices_asc = sorted(prices, key=lambda x: x[0])
        closes = [p[1] for p in prices_asc]
        
        trend_days = 0
        for i in range(len(closes) - 1, 0, -1):  # Start from most recent
            if closes[i] > closes[i-1]:
                trend_days += 1
            else:
                break
        
        return trend_days
    
    @staticmethod
    def calculate_for_ticker(
        db: Session, 
        ticker: str, 
        target_date: date,
        lookback_days: int = 100
    ) -> MomentumMetrics:
        """
        Calculate momentum features for a ticker on a specific date
        
        Args:
            db: Database session
            ticker: Stock ticker symbol
            target_date: Date to calculate features for
            lookback_days: Days of price history to fetch
            
        Returns:
            MomentumMetrics with calculated features
        """
        
        # Get stock ID
        stock = db.query(Stock).filter(Stock.symbol == ticker).first()
        if not stock:
            return MomentumMetrics()
        
        # Get price data
        start_date = target_date - timedelta(days=lookback_days)
        
        prices_query = db.query(Price.ts, Price.close, Price.volume).filter(
            Price.stock_id == stock.id,
            func.date(Price.ts) >= start_date,
            func.date(Price.ts) <= target_date
        ).order_by(Price.ts.desc())
        
        price_data = prices_query.all()
        
        if not price_data:
            return MomentumMetrics()
        
        # Extract prices and volumes
        prices = [(p.ts.date(), float(p.close)) for p in price_data]
        volumes = [(p.ts.date(), float(p.volume)) for p in price_data if p.volume]
        
        metrics = MomentumMetrics()
        
        # Calculate returns and momentum
        returns = MomentumFeatures.calculate_returns(prices)
        metrics.ret_1d = returns["ret_1d"]
        metrics.ret_5d = returns["ret_5d"] 
        metrics.ret_20d = returns["ret_20d"]
        metrics.momentum_14d = returns["momentum_14d"]
        
        # Calculate volume z-score
        if volumes:
            metrics.vol_z = MomentumFeatures.calculate_volume_zscore(volumes)
        
        # Calculate volatility
        metrics.volatility_20d = MomentumFeatures.calculate_volatility(prices)
        
        # Count trend days
        metrics.price_trend_days = MomentumFeatures.count_trend_days(prices)
        
        return metrics
    
    @staticmethod
    def calculate_bulk(
        db: Session,
        tickers: List[str],
        target_date: date
    ) -> Dict[str, MomentumMetrics]:
        """
        Calculate momentum features for multiple tickers efficiently
        
        Args:
            db: Database session
            tickers: List of ticker symbols
            target_date: Date to calculate features for
            
        Returns:
            Dictionary mapping ticker -> MomentumMetrics
        """
        results = {}
        
        # TODO: Optimize with bulk queries when we have more data
        for ticker in tickers:
            results[ticker] = MomentumFeatures.calculate_for_ticker(
                db, ticker, target_date
            )
        
        return results
    
    @staticmethod
    def get_market_baseline(db: Session, days: int = 30) -> Dict[str, float]:
        """
        Get market-wide statistics for normalization
        
        Args:
            db: Database session
            days: Number of days to analyze
            
        Returns:
            Dictionary with market statistics
        """
        cutoff_date = date.today() - timedelta(days=days)
        
        # Get all recent prices for market baseline
        recent_prices = db.query(Price).filter(
            func.date(Price.ts) >= cutoff_date
        ).all()
        
        if not recent_prices:
            return {"avg_volatility": 0.2, "avg_volume_ratio": 1.0}
        
        # Calculate market averages (simplified)
        volumes = [float(p.volume) for p in recent_prices if p.volume and p.volume > 0]
        
        return {
            "avg_volume_ratio": 1.0,  # Placeholder
            "sample_count": len(recent_prices),
            "volume_count": len(volumes)
        }
