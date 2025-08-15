"""
Stonks FastAPI Application
Minimal placeholder for Docker build testing
"""
from fastapi import FastAPI

app = FastAPI(title="Stonks API", version="0.1.0")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    """Readiness check endpoint"""
    return {"status": "ready"}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Stonks API - Coming Soon!"}
