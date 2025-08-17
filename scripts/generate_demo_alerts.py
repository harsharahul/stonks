#!/usr/bin/env python3
"""
Generate demo alerts that meet threshold criteria for real-time demonstration
"""

import sys
import os
import asyncio
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
from app.services.websocket_manager import event_broadcaster


def create_high_threshold_signals(db: SessionLocal) -> List[Signal]:
    """Create signals with high strength/confidence to trigger alerts"""
    
    # Get some active stocks
    stocks = db.query(Stock).limit(5).all()
    
    test_signals = []
    
    # Create signals that will definitely trigger alerts
    signal_configs = [
        # Strong buy signal - should trigger strong_signal alert
        {
            "signal_type": "strong_buy",
            "strength": 0.95,  # Above 0.7 threshold
            "confidence": 0.85,  # Above 0.6 threshold
            "direction": "buy",
            "title": "Strong Buy Signal",
            "description": "High confidence buy signal based on technical analysis"
        },
        # Volume spike - should trigger volume_spike alert
        {
            "signal_type": "volume_spike",
            "strength": 0.85,  # Above 0.5 threshold
            "confidence": 0.75,  # Above 0.6 threshold
            "direction": "buy",
            "title": "Volume Spike Detected",
            "description": "Unusual volume activity detected"
        },
        # Breaking news - should trigger breaking_news alert
        {
            "signal_type": "breaking_news",
            "strength": 0.90,  # Above 0.7 threshold
            "confidence": 0.80,  # Above 0.5 threshold
            "direction": "neutral",
            "title": "Breaking News Alert",
            "description": "High novelty content detected"
        },
        # Retail buzz - should trigger retail_buzz alert
        {
            "signal_type": "retail_buzz",
            "strength": 0.75,  # Above 0.6 threshold
            "confidence": 0.70,  # Above 0.5 threshold
            "direction": "buy",
            "title": "Retail Buzz Alert",
            "description": "High WSB engagement detected"
        },
        # WSB trending - should trigger wsb_trending alert
        {
            "signal_type": "wsb_trending",
            "strength": 0.80,  # Above 0.7 threshold
            "confidence": 0.75,  # Above 0.6 threshold
            "direction": "buy",
            "title": "WSB Trending Alert",
            "description": "Stock trending on WallStreetBets"
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
            timeframe="daily",
            signal_metadata={
                "source": "demo_generation",
                "test_data": True,
                "generated_at": datetime.utcnow().isoformat(),
                "title": config["title"],
                "description": config["description"],
                "wsb_mentions": 150 + i * 20,
                "wsb_sentiment": config["strength"],
                "vol_z": 3.5 + i * 0.5,
                "meme_score": config["strength"]
            }
        )
        
        db.add(signal)
        test_signals.append(signal)
    
    db.commit()
    return test_signals


def main():
    """Main function to generate demo alerts"""
    print("🚀 Starting demo alerts generation")
    
    try:
        # Create database session
        db = SessionLocal()
        
        print("📊 Creating high-threshold signals...")
        signals = create_high_threshold_signals(db)
        print(f"✅ Created {len(signals)} high-threshold signals")
        
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
                # Broadcast alert using the correct method
                alert_data = alert.to_dict()
                # Note: broadcast_alert is async, so we'll use the connection manager directly
                from app.services.websocket_manager import connection_manager
                from app.services.websocket_manager import WebSocketMessage
                
                message = WebSocketMessage(
                    type="alert",
                    channel="alerts",
                    data=alert_data,
                    timestamp=datetime.utcnow().isoformat()
                )
                
                # Broadcast to alerts channel
                import asyncio
                asyncio.run(connection_manager.broadcast_to_channel("alerts", message))
                print(f"  📢 Broadcasted alert: {alert.ticker} - {alert.alert_type}")
            except Exception as e:
                print(f"  ❌ Failed to broadcast alert {alert.id}: {e}")
        
        print(f"\n📋 Demo Summary:")
        print(f"   Signals created: {len(signals)}")
        print(f"   Alerts generated: {len(alerts)}")
        print(f"   Tickers involved: {[s.ticker for s in signals]}")
        
        print(f"\n🌐 WebSocket Test URLs:")
        print(f"   Alerts: ws://localhost:8080/api/v1/ws/alerts")
        print(f"   Market: ws://localhost:8080/api/v1/ws/market")
        print(f"   Anomalies: ws://localhost:8080/api/v1/ws/anomalies")
        
        print("\n✅ Demo alerts generation completed!")
        print("   Check the frontend to see real-time alerts!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
