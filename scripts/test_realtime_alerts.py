#!/usr/bin/env python3
"""
Test script to generate signals and alerts for real-time demonstration
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
from typing import List

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models.signal import Signal
from app.models.alert import Alert
from app.models.stock import Stock
from app.services.alert_engine import AlertEngine
from app.services.websocket_manager import event_broadcaster


def create_test_signals(db: SessionLocal) -> List[Signal]:
    """Create test signals for demonstration"""
    
    # Get some active stocks
    stocks = db.query(Stock).limit(5).all()
    
    test_signals = []
    
    for i, stock in enumerate(stocks):
        # Create different types of signals for demonstration
        signal_configs = [
            {
                "signal_type": "momentum_bullish",
                "strength": 0.75 + (i * 0.05),  # Varying strength
                "confidence": 0.8,
                "direction": "bullish",
                "metadata": {"vol_z": 2.5 + i, "article_count_7d": 15 + i * 2}
            },
            {
                "signal_type": "sentiment_spike", 
                "strength": 0.65 + (i * 0.03),
                "confidence": 0.7,
                "direction": "bullish",
                "metadata": {"sent_mean_7d": 0.7 + (i * 0.05), "article_count_7d": 20 + i * 3}
            }
        ]
        
        if i == 0:  # Add a critical WSB signal for first stock
            signal_configs.append({
                "signal_type": "wsb_viral",
                "strength": 0.95,
                "confidence": 0.9,
                "direction": "bullish", 
                "metadata": {"wsb_mention_count_7d": 50, "meme_score": 0.9}
            })
        
        for config in signal_configs:
            signal = Signal(
                ticker=stock.symbol,
                signal_type=config["signal_type"],
                strength=config["strength"],
                confidence=config["confidence"],
                direction=config["direction"],
                timeframe="daily",
                expires_at=datetime.utcnow() + timedelta(hours=24),
                model_version="test_v1.0.0",
                signal_metadata=config["metadata"],
                features_snapshot={
                    "vol_z": config["metadata"].get("vol_z", 1.0),
                    "sent_mean_7d": config["metadata"].get("sent_mean_7d", 0.5),
                    "wsb_sentiment_7d": config["metadata"].get("wsb_sentiment_7d", 0.5),
                    "meme_stock_indicator": config["metadata"].get("meme_score", 0.1)
                }
            )
            test_signals.append(signal)
    
    return test_signals


async def broadcast_test_alerts(alerts: List[Alert]):
    """Broadcast test alerts via WebSocket"""
    
    for alert in alerts:
        alert_data = alert.to_dict()
        
        # Broadcast to global alerts channel
        await event_broadcaster.broadcast_alert(alert_data)
        
        print(f"📡 Broadcasted alert: {alert.ticker} - {alert.title}")
        
        # Small delay between alerts for better UX
        await asyncio.sleep(1)


def main():
    """Main test function"""
    db = SessionLocal()
    
    try:
        print("🚀 Starting real-time alerts test")
        
        # Create test signals
        print("📊 Creating test signals...")
        test_signals = create_test_signals(db)
        
        if not test_signals:
            print("❌ No stocks found to create test signals")
            return
        
        # Save signals to database
        for signal in test_signals:
            db.add(signal)
        db.commit()
        
        print(f"✅ Created {len(test_signals)} test signals")
        
        # Generate alerts from signals
        print("🔔 Generating alerts...")
        alert_engine = AlertEngine(db)
        alerts = alert_engine.process_signals(test_signals)
        alerts_saved = alert_engine.save_alerts(alerts)
        
        print(f"✅ Generated {alerts_saved} alerts")
        
        # Broadcast alerts via WebSocket
        if alerts:
            print("📡 Broadcasting alerts via WebSocket...")
            asyncio.run(broadcast_test_alerts(alerts))
            print("✅ Alerts broadcasted")
        else:
            print("ℹ️ No alerts generated (signals may not meet thresholds)")
        
        # Print summary
        print("\n📋 Test Summary:")
        print(f"   Signals created: {len(test_signals)}")
        print(f"   Alerts generated: {alerts_saved}")
        print(f"   Tickers involved: {list(set(s.ticker for s in test_signals))}")
        
        print("\n🌐 WebSocket Test URLs:")
        print("   Alerts: ws://localhost:8080/api/v1/ws/alerts")
        print("   Market: ws://localhost:8080/api/v1/ws/market")
        print("   Anomalies: ws://localhost:8080/api/v1/ws/anomalies")
        
        print("\n✅ Real-time alerts test completed!")
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        db.rollback()
        raise
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
