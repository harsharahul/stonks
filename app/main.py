"""
Stonks FastAPI Application
Stock Tracker & Analyzer API
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import time

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.metrics import record_request_metrics
from app.api.dependencies import enforce_rate_limit

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

# Best-effort global rate limit before routing
@app.middleware("http")
async def global_rate_limit_middleware(request: Request, call_next):
    try:
        await enforce_rate_limit(request)
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    return await call_next(request)

# Add metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Record metrics for all requests
    record_request_metrics(request, response, duration)
    
    return response

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
