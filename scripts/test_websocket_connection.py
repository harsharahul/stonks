#!/usr/bin/env python3
"""
Test WebSocket connection and real-time alerts
"""

import asyncio
import websockets
import json
from datetime import datetime


async def test_websocket_alerts():
    """Test WebSocket alerts connection"""
    
    uri = "ws://localhost:8080/api/v1/ws/alerts"
    
    try:
        print(f"🔌 Connecting to {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to alerts WebSocket")
            
            # Listen for messages for 30 seconds
            try:
                await asyncio.wait_for(
                    listen_for_messages(websocket),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                print("⏰ Test completed (30 second timeout)")
                
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")


async def listen_for_messages(websocket):
    """Listen for incoming WebSocket messages"""
    
    # Send a test ping
    ping_msg = {
        "type": "ping",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await websocket.send(json.dumps(ping_msg))
    print("📤 Sent ping message")
    
    message_count = 0
    
    async for message in websocket:
        try:
            data = json.loads(message)
            message_count += 1
            
            print(f"📥 Message {message_count}: {data.get('type', 'unknown')}")
            
            if data.get("type") == "connection":
                print(f"   ✅ Connection confirmed: {data.get('data', {}).get('status')}")
            elif data.get("type") == "pong":
                print(f"   🏓 Pong received: {data.get('data', {}).get('timestamp')}")
            elif data.get("type") == "alert":
                alert = data.get("data", {})
                print(f"   🚨 Alert: {alert.get('ticker')} - {alert.get('title')}")
                print(f"      Severity: {alert.get('severity')}, Type: {alert.get('alert_type')}")
                
                # Acknowledge the alert
                ack_msg = {
                    "type": "acknowledge_alert",
                    "alert_id": alert.get("id")
                }
                await websocket.send(json.dumps(ack_msg))
                print(f"   ✅ Acknowledged alert {alert.get('id')}")
            else:
                print(f"   📋 Other message: {json.dumps(data, indent=2)}")
                
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing message: {e}")
            print(f"   Raw message: {message}")


async def test_market_websocket():
    """Test market overview WebSocket"""
    
    uri = "ws://localhost:8080/api/v1/ws/market"
    
    try:
        print(f"🔌 Connecting to market WebSocket: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to market WebSocket")
            
            # Listen for initial market overview
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                data = json.loads(message)
                
                if data.get("type") == "connection":
                    print("   ✅ Market connection confirmed")
                elif data.get("type") == "market_overview":
                    overview = data.get("data", {})
                    print(f"   📊 Market overview received:")
                    print(f"      Top signals: {len(overview.get('top_signals', []))}")
                    print(f"      Recent alerts: {len(overview.get('recent_alerts', []))}")
                    print(f"      Alert stats: {overview.get('alert_stats', {})}")
                
            except asyncio.TimeoutError:
                print("⏰ No initial market data received")
                
    except Exception as e:
        print(f"❌ Market WebSocket connection failed: {e}")


async def main():
    """Run all WebSocket tests"""
    
    print("🚀 Starting WebSocket tests")
    print("=" * 50)
    
    # Test alerts WebSocket
    print("\n📡 Testing Alerts WebSocket")
    await test_websocket_alerts()
    
    print("\n📊 Testing Market WebSocket")
    await test_market_websocket()
    
    print("\n✅ WebSocket tests completed")


if __name__ == "__main__":
    asyncio.run(main())
