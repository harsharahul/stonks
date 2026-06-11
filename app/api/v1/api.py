"""
API v1 Router
Main router that includes all API endpoints
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    stocks, feed, recommendations, signals, admin, features, metrics,
    anomalies, websockets, market_analysis,
    stocks_enhanced, prices, auth, users, desk, broker, strategies,
    consolidated,
)

# Create API router
api_router = APIRouter()

# Public endpoints
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(feed.router, prefix="/feed", tags=["feed"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
api_router.include_router(anomalies.router, prefix="/anomalies", tags=["anomalies"])
api_router.include_router(websockets.router, prefix="/ws", tags=["websockets"])
api_router.include_router(features.router, prefix="/features", tags=["features"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(market_analysis.router, prefix="/market-analysis", tags=["market-analysis"])
api_router.include_router(stocks_enhanced.router, prefix="/stocks-enhanced", tags=["stocks-enhanced"])
api_router.include_router(prices.router, prefix="/prices", tags=["prices"])
api_router.include_router(desk.router, prefix="/desk", tags=["ai-trading-desk"])
api_router.include_router(consolidated.router, prefix="/consolidated", tags=["consolidated"])

# Authenticated endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(broker.router, prefix="/broker", tags=["broker"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])

# Admin-only endpoints (protected via require_admin dependency inside admin.py)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])


# Health/ready endpoints (duplicated from root so they're reachable via /api/v1/ in k3s ingress)
@api_router.get("/health", tags=["system"])
async def health():
    return {"status": "healthy", "service": "stonks-api"}


@api_router.get("/ready", tags=["system"])
async def ready():
    return {"status": "ready", "service": "stonks-api"}
