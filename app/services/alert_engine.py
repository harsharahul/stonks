"""
Alert Engine

Converts signals into actionable alerts based on configurable rules and user preferences.
Handles alert throttling, severity scoring, and multi-channel delivery.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.signal import Signal
from app.models.alert import Alert, AlertSubscription
from app.models.ticker_features_daily import TickerFeaturesDaily

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """Configuration for alert generation from signals"""
    alert_type: str
    signal_types: List[str]  # Which signal types trigger this alert
    min_strength: float
    min_confidence: float
    severity_thresholds: Dict[str, float]  # strength thresholds for each severity
    cooldown_hours: int  # Minimum time between alerts of same type for same ticker
    title_template: str
    message_template: str


class AlertEngine:
    """
    Main alert engine that converts signals into user-facing alerts
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.rules = self._load_alert_rules()
    
    def _load_alert_rules(self) -> List[AlertRule]:
        """Load alert generation rules"""
        return [
            # Strong momentum alerts
            AlertRule(
                alert_type="momentum_breakout",
                signal_types=["momentum_bullish", "momentum_bearish"],
                min_strength=0.6,
                min_confidence=0.5,
                severity_thresholds={"high": 0.8, "medium": 0.6},
                cooldown_hours=6,
                title_template="{ticker} Momentum Breakout",
                message_template="{ticker} showing {direction} momentum with {strength} strength. Volume up {vol_z:.1f}x normal."
            ),
            
            # Sentiment spike alerts
            AlertRule(
                alert_type="sentiment_spike",
                signal_types=["sentiment_spike"],
                min_strength=0.5,
                min_confidence=0.4,
                severity_thresholds={"high": 0.8, "medium": 0.6},
                cooldown_hours=4,
                title_template="{ticker} Sentiment Spike",
                message_template="{ticker} sentiment {direction} spike detected. {article_count} articles in last 7 days."
            ),
            
            # WSB viral alerts
            AlertRule(
                alert_type="wsb_viral",
                signal_types=["wsb_viral"],
                min_strength=0.7,
                min_confidence=0.6,
                severity_thresholds={"critical": 0.9, "high": 0.8, "medium": 0.7},
                cooldown_hours=3,
                title_template="{ticker} Going Viral on WSB",
                message_template="{ticker} trending on WallStreetBets with {wsb_mentions} mentions. Meme score: {meme_score:.0%}"
            ),
            
            # Retail buzz alerts
            AlertRule(
                alert_type="retail_buzz",
                signal_types=["retail_buzz"],
                min_strength=0.6,
                min_confidence=0.5,
                severity_thresholds={"high": 0.8, "medium": 0.6},
                cooldown_hours=8,
                title_template="{ticker} Retail Buzz",
                message_template="{ticker} generating retail buzz. WSB sentiment: {wsb_sentiment:.0%}, engagement high."
            ),
            
            # Volume spike alerts
            AlertRule(
                alert_type="volume_spike",
                signal_types=["volume_spike"],
                min_strength=0.5,
                min_confidence=0.6,
                severity_thresholds={"high": 0.8, "medium": 0.5},
                cooldown_hours=2,
                title_template="{ticker} Volume Spike",
                message_template="{ticker} volume {vol_z:.1f}x normal. Price {direction}."
            ),
            
            # Breaking news alerts
            AlertRule(
                alert_type="breaking_news",
                signal_types=["breaking_news"],
                min_strength=0.7,
                min_confidence=0.5,
                severity_thresholds={"high": 0.8, "medium": 0.7},
                cooldown_hours=6,
                title_template="{ticker} Breaking News",
                message_template="{ticker} in breaking news. High novelty content detected."
            ),
            
            # Strong buy/sell alerts
            AlertRule(
                alert_type="strong_signal",
                signal_types=["strong_buy", "strong_sell"],
                min_strength=0.7,
                min_confidence=0.6,
                severity_thresholds={"critical": 0.9, "high": 0.8, "medium": 0.7},
                cooldown_hours=12,
                title_template="{ticker} Strong {direction} Signal",
                message_template="{ticker} triggered strong {direction} signal. Strength: {strength:.0%}, Confidence: {confidence:.0%}"
            ),
            
            # Divergence alerts
            AlertRule(
                alert_type="sentiment_momentum_divergence",
                signal_types=["sentiment_momentum_divergence"],
                min_strength=0.5,
                min_confidence=0.4,
                severity_thresholds={"high": 0.7, "medium": 0.5},
                cooldown_hours=24,
                title_template="{ticker} Sentiment-Price Divergence",
                message_template="{ticker} showing divergence between sentiment and price action. Potential reversal signal."
            )
        ]
    
    def process_signals(self, signals: List[Signal]) -> List[Alert]:
        """
        Process a list of signals and generate appropriate alerts
        """
        alerts = []
        
        for signal in signals:
            try:
                alert = self._evaluate_signal_for_alerts(signal)
                if alert:
                    alerts.append(alert)
            except Exception as e:
                logger.error(f"Error processing signal {signal.id}: {e}")
                continue
        
        return alerts
    
    def _evaluate_signal_for_alerts(self, signal: Signal) -> Optional[Alert]:
        """
        Evaluate a single signal against alert rules
        """
        # Find matching alert rule
        matching_rule = None
        for rule in self.rules:
            if signal.signal_type in rule.signal_types:
                matching_rule = rule
                break
        
        if not matching_rule:
            return None
        
        # Check strength and confidence thresholds
        if signal.strength < matching_rule.min_strength:
            return None
        if signal.confidence < matching_rule.min_confidence:
            return None
        
        # Check cooldown period
        if self._is_in_cooldown(signal.ticker, matching_rule.alert_type, matching_rule.cooldown_hours):
            logger.debug(f"Alert {matching_rule.alert_type} for {signal.ticker} in cooldown")
            return None
        
        # Determine severity
        severity = self._calculate_severity(signal.strength, matching_rule.severity_thresholds)
        
        # Generate alert content
        title, message = self._generate_alert_content(signal, matching_rule)
        
        # Create alert
        alert = Alert(
            ticker=signal.ticker,
            alert_type=matching_rule.alert_type,
            severity=severity,
            title=title,
            message=message,
            signal_id=signal.id,
            alert_metadata={
                "signal_type": signal.signal_type,
                "signal_strength": float(signal.strength),  # Convert Decimal to float
                "signal_confidence": float(signal.confidence),  # Convert Decimal to float
                "signal_direction": signal.direction,
                "rule_matched": matching_rule.alert_type
            }
        )
        
        return alert
    
    def _is_in_cooldown(self, ticker: str, alert_type: str, cooldown_hours: int) -> bool:
        """
        Check if an alert type is in cooldown period for a ticker
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=cooldown_hours)
        
        recent_alert = self.db.query(Alert).filter(
            and_(
                Alert.ticker == ticker,
                Alert.alert_type == alert_type,
                Alert.triggered_at > cutoff_time
            )
        ).first()
        
        return recent_alert is not None
    
    def _calculate_severity(self, strength: float, thresholds: Dict[str, float]) -> str:
        """
        Calculate alert severity based on signal strength and thresholds
        """
        abs_strength = abs(strength)
        
        if "critical" in thresholds and abs_strength >= thresholds["critical"]:
            return "critical"
        elif "high" in thresholds and abs_strength >= thresholds["high"]:
            return "high"
        elif "medium" in thresholds and abs_strength >= thresholds["medium"]:
            return "medium"
        else:
            return "low"
    
    def _generate_alert_content(self, signal: Signal, rule: AlertRule) -> tuple[str, str]:
        """
        Generate alert title and message from templates
        """
        # Get additional context from features snapshot
        features_data = signal.features_snapshot or {}
        
        # Prepare template variables
        template_vars = {
            "ticker": signal.ticker,
            "direction": signal.direction,
            "strength": signal.strength,
            "confidence": signal.confidence,
            "vol_z": features_data.get("vol_z", 0),
            "wsb_mentions": signal.signal_metadata.get("wsb_mention_count_7d", 0) if signal.signal_metadata else 0,
            "wsb_sentiment": features_data.get("wsb_sentiment_7d", 0.5),
            "meme_score": features_data.get("meme_stock_indicator", 0),
            "article_count": signal.signal_metadata.get("article_count_7d", 0) if signal.signal_metadata else 0
        }
        
        try:
            title = rule.title_template.format(**template_vars)
            message = rule.message_template.format(**template_vars)
        except KeyError as e:
            logger.warning(f"Missing template variable {e} for alert {rule.alert_type}")
            title = f"{signal.ticker} {rule.alert_type.replace('_', ' ').title()}"
            message = f"{signal.ticker} triggered {signal.signal_type} signal with {signal.strength:.0%} strength."
        
        return title, message
    
    def save_alerts(self, alerts: List[Alert]) -> int:
        """
        Save alerts to database
        """
        if not alerts:
            return 0
        
        try:
            for alert in alerts:
                self.db.add(alert)
            
            self.db.commit()
            logger.info(f"Saved {len(alerts)} alerts to database")
            return len(alerts)
            
        except Exception as e:
            logger.error(f"Error saving alerts: {e}")
            self.db.rollback()
            raise
    
    def get_recent_alerts(self, hours: int = 24, ticker: str = None, limit: int = 100) -> List[Alert]:
        """
        Get recent alerts within specified time window
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(Alert).filter(
            Alert.triggered_at > cutoff_time
        )
        
        if ticker:
            query = query.filter(Alert.ticker == ticker.upper())
        
        return query.order_by(Alert.triggered_at.desc()).limit(limit).all()
    
    def get_unacknowledged_alerts(self, user_id: str = None, limit: int = 50) -> List[Alert]:
        """
        Get unacknowledged alerts for a user or system-wide
        """
        query = self.db.query(Alert).filter(
            Alert.acknowledged_at.is_(None)
        )
        
        if user_id:
            query = query.filter(Alert.user_id == user_id)
        
        return query.order_by(Alert.triggered_at.desc()).limit(limit).all()
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Mark an alert as acknowledged
        """
        try:
            alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
            if alert:
                alert.acknowledge()
                self.db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error acknowledging alert {alert_id}: {e}")
            self.db.rollback()
            return False
    
    def get_alert_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get alert statistics for the specified period
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        # Total alerts
        total_alerts = self.db.query(func.count(Alert.id)).filter(
            Alert.triggered_at > cutoff_time
        ).scalar()
        
        # Alerts by severity
        severity_stats = self.db.query(
            Alert.severity,
            func.count(Alert.id).label('count')
        ).filter(
            Alert.triggered_at > cutoff_time
        ).group_by(Alert.severity).all()
        
        # Alerts by type
        type_stats = self.db.query(
            Alert.alert_type,
            func.count(Alert.id).label('count')
        ).filter(
            Alert.triggered_at > cutoff_time
        ).group_by(Alert.alert_type).order_by(func.count(Alert.id).desc()).limit(10).all()
        
        # Acknowledgment rate
        acknowledged_count = self.db.query(func.count(Alert.id)).filter(
            and_(
                Alert.triggered_at > cutoff_time,
                Alert.acknowledged_at.isnot(None)
            )
        ).scalar()
        
        acknowledgment_rate = (acknowledged_count / total_alerts * 100) if total_alerts > 0 else 0
        
        return {
            "period_days": days,
            "total_alerts": total_alerts,
            "acknowledgment_rate": round(acknowledgment_rate, 1),
            "severity_breakdown": {severity: count for severity, count in severity_stats},
            "top_alert_types": [{"type": alert_type, "count": count} for alert_type, count in type_stats],
            "unacknowledged_count": total_alerts - acknowledged_count
        }
