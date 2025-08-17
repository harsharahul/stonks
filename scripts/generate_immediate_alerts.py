#!/usr/bin/env python3
"""
Generate immediate alerts that will trigger real-time notifications
"""

import sys
import os
from datetime import datetime, timedelta
from typing import List
from decimal import Decimal

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.models.signal import Signal
from app.models.alert import Alert
from app.models.stock import Stock
from app.services.alert_engine import AlertEngine
from app.services.websocket_manager import connection_manager, WebSocketMessage


def create_immediate_signals(db: SessionLocal) -> List[Signal]:
    """Create signals that will immediately trigger alerts"""
    
    # Get some active stocks
    stocks = db.query(Stock).limit(5).all()
    
    test_signals = []
    
    # Create signals with correct types that will trigger alerts
    signal_configs = [
        # Sentiment spike - should trigger sentiment_spike alert
        {
            "signal_type": "sentiment_spike",
            "strength": 0.85,  # Above 0.5 threshold
            "confidence": 0.75,  # Above 0.4 threshold
            "direction": "bullish",
            "timeframe": "daily"
        },
        # WSB viral - should trigger wsb_viral alert
        {
            "signal_type": "wsb_viral",
            "strength": 0.90,  # Above 0.7 threshold
            "confidence": 0.80,  # Above 0.6 threshold
            "direction": "bullish",
            "timeframe": "daily"
        },
        # Momentum bullish - should trigger momentum_breakout alert
        {
            "signal_type": "momentum_bullish",
            "strength": 0.75,  # Above 0.6 threshold
            "confidence": 0.70,  # Above 0.5 threshold
            "direction": "bullish",
            "timeframe": "daily"
        },
        # Sentiment momentum divergence - should trigger divergence alert
        {
            "signal_type": "sentiment_momentum_divergence",
            "strength": 0.65,  # Above 0.5 threshold
            "confidence": 0.60,  # Above 0.4 threshold
            "direction": "neutral",
            "timeframe": "daily"
        },
        # Strong sell - should trigger strong_signal alert
        {
            "signal_type": "strong_sell",
            "strength": 0.85,  # Above 0.7 threshold
            "confidence": 0.75,  # Above 0.6 threshold
            "direction": "bearish",
            "timeframe": "daily"
        }
    ]
    
    for i, stock in enumerate(stocks):
        config = signal_configs[i % len(signal_configs)]
        
        signal = Signal(
            ticker=stock.symbol,
            signal_type=config["signal_type"],
            strength=Decimal(str(config["strength"])),
            confidence=Decimal(str(config["confidence"])),
            direction=config["direction"],
            timeframe=config["timeframe"],
            signal_metadata={
                "source": "immediate_demo",
                "test_data": True,
                "generated_at": datetime.utcnow().isoformat(),
                "wsb_mentions": 200 + i * 30,
                "wsb_sentiment": config["strength"],
                "vol_z": 4.0 + i * 0.5,
                "meme_score": config["strength"],
                "article_count_7d": 15 + i * 5
            }
        )
        
        db.add(signal)
        test_signals.append(signal)
    
    db.commit()
    return test_signals


def main():
    """Main function to generate immediate alerts"""
    print("🚀 Starting immediate alerts generation")
    
    try:
        # Create database session
        db = SessionLocal()
        
        print("📊 Creating immediate signals...")
        signals = create_immediate_signals(db)
        print(f"✅ Created {len(signals)} immediate signals")
        
        print("🔔 Processing signals through alert engine...")
        alert_engine = AlertEngine(db)
        alerts = alert_engine.process_signals(signals)
        print(f"✅ Generated {len(alerts)} alerts")
        
        # Save alerts to database
        for alert in alerts:
            db.add(alert)
        db.commit()
        
        print("📡 Broadcasting alerts via WebSocket...")
        for alert in alerts:
            try:
                # Create WebSocket message
                message = WebSocketMessage(
                    type="alert",
                    channel="alerts",
                    data=alert.to_dict(),
                    timestamp=datetime.utcnow().isoformat()
                )
                
                # Broadcast to alerts channel
                import asyncio
                asyncio.run(connection_manager.broadcast_to_channel("alerts", message))
                print(f"  📢 Broadcasted alert: {alert.ticker} - {alert.alert_type} ({alert.severity})")
            except Exception as e:
                print(f"  ❌ Failed to broadcast alert {alert.id}: {e}")
        
        print(f"\n📋 Immediate Alerts Summary:")
        print(f"   Signals created: {len(signals)}")
        print(f"   Alerts generated: {len(alerts)}")
        print(f"   Tickers involved: {[s.ticker for s in signals]}")
        
        if alerts:
            print(f"\n🔔 Alert Details:")
            for alert in alerts:
                print(f"   • {alert.ticker}: {alert.title} ({alert.severity})")
        
        print(f"\n🌐 WebSocket Test URLs:")
        print(f"   Alerts: ws://localhost:8080/api/v1/ws/alerts")
        print(f"   Market: ws://localhost:8080/api/v1/ws/market")
        print(f"   Anomalies: ws://localhost:8080/api/v1/ws/anomalies")
        
        print("\n✅ Immediate alerts generation completed!")
        print("   Check the frontend to see real-time alerts!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
