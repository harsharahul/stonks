"""
Stonks FastAPI Application
Stock Tracker & Analyzer API
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.api import api_router

# Create FastAPI application
app = FastAPI(
    title="Stonks API",
    description="Stock Tracker & Analyzer - Aggregating market signals for daily recommendations",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "stonks-api"}


@app.get("/ready")
async def ready():
    """Readiness check endpoint - checks database connectivity"""
    # TODO: Add database connectivity check
    return {"status": "ready", "service": "stonks-api"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Stonks API",
        "description": "Stock Tracker & Analyzer",
        "version": "0.1.0",
        "docs_url": "/docs",
        "api_url": settings.API_V1_STR
    }
