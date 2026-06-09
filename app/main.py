"""
Stonks FastAPI Application
Stock Tracker & Analyzer API
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import time
import uuid
import logging

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.metrics import record_request_metrics
from app.api.dependencies import enforce_rate_limit
from app.core.error_handlers import setup_error_handlers

# Create FastAPI application
app = FastAPI(
    title="Stonks API",
    description="Stock Tracker & Analyzer - Aggregating market signals for daily recommendations",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Setup enhanced error handling
setup_error_handlers(app)

# CORS — restrict to known origins in production
_cors_origins = [
    "https://stonks.internal.example.com",
    "http://localhost:3000",
    "http://localhost:5173",  # Vite dev server
    "http://localhost:8080",
]
# In development, allow all origins for convenience
_cors_allow_all = settings.ENVIRONMENT == "development"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _cors_allow_all else _cors_origins,
    allow_credentials=not _cors_allow_all,  # credentials + wildcard origins is invalid
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-API-Key"],
)

# Request ID middleware for error tracking
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response

# Best-effort global rate limit before routing
@app.middleware("http")
async def global_rate_limit_middleware(request: Request, call_next):
    try:
        await enforce_rate_limit(request)
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429, 
            content={
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
                "details": {"request_id": getattr(request.state, "request_id", None)},
                "timestamp": time.time()
            }
        )
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

# M2: Validate ENVIRONMENT is a known value
_VALID_ENVIRONMENTS = {"development", "staging", "production"}
if settings.ENVIRONMENT not in _VALID_ENVIRONMENTS:
    raise ValueError(
        f"ENVIRONMENT={settings.ENVIRONMENT!r} is not valid. "
        f"Must be one of: {', '.join(sorted(_VALID_ENVIRONMENTS))}"
    )

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# H5: Validate OIDC config at startup to catch partial config early
@app.on_event("startup")
async def _validate_oidc_config():
    from app.api.dependencies import is_oidc_configured
    try:
        configured = is_oidc_configured()
        if configured:
            logging.getLogger(__name__).info("OIDC configured: issuer=%s", settings.OIDC_ISSUER_URL)
        else:
            logging.getLogger(__name__).info("OIDC not configured — running without authentication")
    except ValueError as e:
        logging.getLogger(__name__).error("OIDC config error: %s", e)
        raise


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
