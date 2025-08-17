"""
Signal Generation Engine

Converts analytics features into actionable trading signals with strength and confidence scoring.
Implements various signal types: momentum, sentiment, WSB viral, news catalysts, etc.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models.signal import Signal
from app.models.alert import Alert
from app.models.ticker_features_daily import TickerFeaturesDaily
from app.models.article import Article
from app.models.stock import Stock

logger = logging.getLogger(__name__)


@dataclass
class SignalRule:
    """Configuration for a signal generation rule"""
    signal_type: str
    condition: str  # Python expression to evaluate
    strength_formula: str  # Formula to calculate signal strength
    confidence_formula: str  # Formula to calculate confidence
    direction_rule: str  # Rule to determine bullish/bearish
    timeframe: str = "daily"
    expires_hours: int = 24
    min_confidence: float = 0.3
    description: str = ""


class SignalGenerator:
    """
    Main signal generation engine that converts features into actionable signals
    """
    
    def __init__(self, db: Session, model_version: str = "v1.0.0"):
        self.db = db
        self.model_version = model_version
        self.rules = self._load_signal_rules()
    
    def _load_signal_rules(self) -> List[SignalRule]:
        """Load signal generation rules"""
        return [
            # Momentum signals
            SignalRule(
                signal_type="momentum_bullish",
                condition="features.momentum_14d > 0.05 and features.vol_z > 1.5",
                strength_formula="min(features.momentum_14d / 0.15, 1.0)",
                confidence_formula="min(features.vol_z / 3.0, 1.0) * 0.8",
                direction_rule="'bullish'",
                description="Strong upward momentum with volume confirmation"
            ),
            
            SignalRule(
                signal_type="momentum_bearish",
                condition="features.momentum_14d < -0.05 and features.vol_z > 1.5",
                strength_formula="min(abs(features.momentum_14d) / 0.15, 1.0)",
                confidence_formula="min(features.vol_z / 3.0, 1.0) * 0.8",
                direction_rule="'bearish'",
                description="Strong downward momentum with volume confirmation"
            ),
            
            # Sentiment signals
            SignalRule(
                signal_type="sentiment_spike",
                condition="features.sent_shock and abs(features.sent_shock) > 2.0",
                strength_formula="min(abs(features.sent_shock) / 3.0, 1.0)",
                confidence_formula="min(features.article_count_7d / 20.0, 1.0)",
                direction_rule="'bullish' if features.sent_shock > 0 else 'bearish'",
                expires_hours=12,
                description="Unusual sentiment change vs historical baseline"
            ),
            
            SignalRule(
                signal_type="sentiment_momentum_divergence",
                condition="features.sent_mean_7d and features.momentum_14d and ((features.sent_mean_7d > 0.7 and features.momentum_14d < -0.03) or (features.sent_mean_7d < 0.3 and features.momentum_14d > 0.03))",
                strength_formula="abs(features.sent_mean_7d - 0.5) + abs(features.momentum_14d)",
                confidence_formula="0.6",
                direction_rule="'bullish' if features.sent_mean_7d > 0.7 else 'bearish'",
                description="Sentiment and price momentum divergence"
            ),
            
            # WSB/Retail sentiment signals
            SignalRule(
                signal_type="wsb_viral",
                condition="features.meme_stock_indicator and features.meme_stock_indicator > 0.8 and features.wsb_mention_count_7d > 5",
                strength_formula="features.meme_stock_indicator",
                confidence_formula="min(features.wsb_engagement_score or 0.5, 1.0)",
                direction_rule="'bullish' if (features.wsb_sentiment_7d or 0.5) > 0.6 else 'neutral'",
                expires_hours=6,
                description="High meme stock potential on WallStreetBets"
            ),
            
            SignalRule(
                signal_type="retail_buzz",
                condition="features.retail_buzz_score and features.retail_buzz_score > 0.7",
                strength_formula="features.retail_buzz_score",
                confidence_formula="min((features.wsb_mention_count_7d or 0) / 10.0, 1.0)",
                direction_rule="'bullish' if (features.wsb_sentiment_7d or 0.5) > 0.6 else 'bearish'",
                expires_hours=8,
                description="High retail investor buzz and engagement"
            ),
            
            # Volume and price action signals
            SignalRule(
                signal_type="volume_spike",
                condition="features.vol_z and features.vol_z > 3.0",
                strength_formula="min(features.vol_z / 5.0, 1.0)",
                confidence_formula="0.7",
                direction_rule="'bullish' if (features.ret_1d or 0) > 0 else 'bearish'",
                expires_hours=4,
                description="Unusual volume spike"
            ),
            
            # Novelty signals
            SignalRule(
                signal_type="breaking_news",
                condition="features.novelty_mean_3d and features.novelty_mean_3d > 0.8",
                strength_formula="features.novelty_mean_3d",
                confidence_formula="min(features.article_count_7d / 15.0, 1.0)",
                direction_rule="'neutral'",  # Direction depends on sentiment
                expires_hours=6,
                description="High novelty in recent news coverage"
            ),
            
            # Composite buy/sell signals
            SignalRule(
                signal_type="strong_buy",
                condition="(features.momentum_14d or 0) > 0.08 and (features.sent_mean_7d or 0.5) > 0.65 and (features.vol_z or 0) > 2.0",
                strength_formula="((features.momentum_14d or 0) + (features.sent_mean_7d or 0.5) - 0.5 + min((features.vol_z or 0) / 5.0, 0.3)) / 1.3",
                confidence_formula="min(features.article_count_7d / 25.0, 1.0) * 0.9",
                direction_rule="'bullish'",
                min_confidence=0.5,
                description="Strong bullish signal across multiple factors"
            ),
            
            SignalRule(
                signal_type="strong_sell",
                condition="(features.momentum_14d or 0) < -0.08 and (features.sent_mean_7d or 0.5) < 0.35 and (features.vol_z or 0) > 2.0",
                strength_formula="(abs(features.momentum_14d or 0) + abs((features.sent_mean_7d or 0.5) - 0.5) + min((features.vol_z or 0) / 5.0, 0.3)) / 1.3",
                confidence_formula="min(features.article_count_7d / 25.0, 1.0) * 0.9",
                direction_rule="'bearish'",
                min_confidence=0.5,
                description="Strong bearish signal across multiple factors"
            )
        ]
    
    def generate_signals_for_ticker(self, ticker: str) -> List[Signal]:
        """
        Generate all applicable signals for a specific ticker
        """
        logger.info(f"Generating signals for {ticker}")
        
        # Get latest features
        features = self._get_latest_features(ticker)
        if not features:
            logger.warning(f"No features found for {ticker}")
            return []
        
        signals = []
        
        for rule in self.rules:
            try:
                signal = self._evaluate_rule(ticker, features, rule)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.signal_type} for {ticker}: {e}")
                continue
        
        logger.info(f"Generated {len(signals)} signals for {ticker}")
        return signals
    
    def _get_latest_features(self, ticker: str) -> Optional[TickerFeaturesDaily]:
        """Get the latest features for a ticker"""
        return self.db.query(TickerFeaturesDaily).filter(
            TickerFeaturesDaily.ticker == ticker.upper()
        ).order_by(TickerFeaturesDaily.date.desc()).first()
    
    def _evaluate_rule(self, ticker: str, features: TickerFeaturesDaily, rule: SignalRule) -> Optional[Signal]:
        """
        Evaluate a single signal rule against features
        """
        try:
            # Create evaluation context
            eval_context = {
                'features': features,
                'min': min,
                'max': max,
                'abs': abs
            }
            
            # Check if condition is met
            condition_result = eval(rule.condition, eval_context)
            if not condition_result:
                return None
            
            # Calculate strength and confidence
            strength = eval(rule.strength_formula, eval_context)
            confidence = eval(rule.confidence_formula, eval_context)
            direction = eval(rule.direction_rule, eval_context)
            
            # Validate ranges
            strength = max(-1.0, min(1.0, float(strength)))
            confidence = max(0.0, min(1.0, float(confidence)))
            
            # Check minimum confidence threshold
            if confidence < rule.min_confidence:
                return None
            
            # Calculate expiry time
            expires_at = datetime.utcnow() + timedelta(hours=rule.expires_hours)
            
            # Create signal
            signal = Signal(
                ticker=ticker.upper(),
                signal_type=rule.signal_type,
                strength=strength,
                confidence=confidence,
                direction=direction,
                timeframe=rule.timeframe,
                expires_at=expires_at,
                model_version=self.model_version,
                signal_metadata={
                    "rule_description": rule.description,
                    "condition": rule.condition,
                    "feature_date": features.date.isoformat() if features.date else None
                },
                features_snapshot={
                    "momentum_14d": float(features.momentum_14d) if features.momentum_14d else None,
                    "sent_mean_7d": float(features.sent_mean_7d) if features.sent_mean_7d else None,
                    "vol_z": float(features.vol_z) if features.vol_z else None,
                    "wsb_sentiment_7d": float(features.wsb_sentiment_7d) if features.wsb_sentiment_7d else None,
                    "meme_stock_indicator": float(features.meme_stock_indicator) if features.meme_stock_indicator else None,
                    "retail_buzz_score": float(features.retail_buzz_score) if features.retail_buzz_score else None
                }
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.signal_type}: {e}")
            return None
    
    def generate_bulk_signals(self, tickers: List[str]) -> Dict[str, List[Signal]]:
        """
        Generate signals for multiple tickers efficiently
        """
        results = {}
        
        for ticker in tickers:
            try:
                signals = self.generate_signals_for_ticker(ticker)
                if signals:
                    results[ticker] = signals
            except Exception as e:
                logger.error(f"Error generating signals for {ticker}: {e}")
                continue
        
        return results
    
    def save_signals(self, signals: List[Signal]) -> int:
        """
        Save signals to database
        Returns number of signals saved
        """
        if not signals:
            return 0
        
        try:
            for signal in signals:
                self.db.add(signal)
            
            self.db.commit()
            logger.info(f"Saved {len(signals)} signals to database")
            return len(signals)
            
        except Exception as e:
            logger.error(f"Error saving signals: {e}")
            self.db.rollback()
            raise
    
    def get_active_signals(self, ticker: str = None, limit: int = 100) -> List[Signal]:
        """
        Get active (non-expired) signals
        """
        query = self.db.query(Signal).filter(
            Signal.expires_at > datetime.utcnow()
        )
        
        if ticker:
            query = query.filter(Signal.ticker == ticker.upper())
        
        return query.order_by(Signal.generated_at.desc()).limit(limit).all()
    
    def get_signal_summary(self, ticker: str) -> Dict[str, Any]:
        """
        Get summary of active signals for a ticker
        """
        active_signals = self.get_active_signals(ticker)
        
        if not active_signals:
            return {
                "ticker": ticker,
                "signal_count": 0,
                "bullish_signals": 0,
                "bearish_signals": 0,
                "neutral_signals": 0,
                "max_strength": 0,
                "avg_confidence": 0,
                "signals": []
            }
        
        bullish = [s for s in active_signals if s.direction == 'bullish']
        bearish = [s for s in active_signals if s.direction == 'bearish']
        neutral = [s for s in active_signals if s.direction == 'neutral']
        
        return {
            "ticker": ticker,
            "signal_count": len(active_signals),
            "bullish_signals": len(bullish),
            "bearish_signals": len(bearish),
            "neutral_signals": len(neutral),
            "max_strength": max(abs(s.strength) for s in active_signals),
            "avg_confidence": sum(s.confidence for s in active_signals) / len(active_signals),
            "signals": [s.to_dict() for s in active_signals]
        }
