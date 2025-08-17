"""
API v1 Router
Main router that includes all API endpoints
"""
from fastapi import APIRouter

from app.api.v1.endpoints import stocks, feed, recommendations, signals, admin, features, metrics, anomalies, websockets

# Create API router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(stocks.router, prefix="/stocks", tags=["stocks"])
api_router.include_router(feed.router, prefix="/feed", tags=["feed"])
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(signals.router, prefix="/signals", tags=["signals"])
api_router.include_router(anomalies.router, prefix="/anomalies", tags=["anomalies"])
api_router.include_router(websockets.router, prefix="/ws", tags=["websockets"])
api_router.include_router(features.router, prefix="/features", tags=["features"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
