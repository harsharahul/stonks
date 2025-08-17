"""
Global Error Handlers for FastAPI Application

Provides centralized error handling, logging, and user-friendly error responses.
"""

import logging
import traceback
from typing import Any, Dict
from datetime import datetime
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import StonksException, create_http_exception, handle_unexpected_error

logger = logging.getLogger(__name__)


async def stonks_exception_handler(request: Request, exc: StonksException) -> JSONResponse:
    """Handle custom Stonks exceptions with proper error formatting"""
    
    http_exc = create_http_exception(exc)
    
    # Add request context to error details
    error_detail = http_exc.detail
    error_detail["request_id"] = getattr(request.state, "request_id", None)
    error_detail["path"] = str(request.url.path)
    error_detail["method"] = request.method
    
    return JSONResponse(
        status_code=http_exc.status_code,
        content=error_detail
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Enhanced HTTP exception handler with better error formatting"""
    
    # Check if it's already a properly formatted error
    if isinstance(exc.detail, dict) and "error_code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # Format simple HTTP exceptions
    error_detail = {
        "error_code": f"HTTP_{exc.status_code}",
        "message": str(exc.detail),
        "technical_message": str(exc.detail),
        "details": {
            "status_code": exc.status_code,
            "path": str(request.url.path),
            "method": request.method
        },
        "timestamp": datetime.utcnow().isoformat(),
        "support_message": "If this issue persists, please contact support."
    }
    
    # Add helpful messages for common HTTP errors
    if exc.status_code == 404:
        error_detail["message"] = "The requested resource was not found."
    elif exc.status_code == 403:
        error_detail["message"] = "You don't have permission to access this resource."
    elif exc.status_code == 401:
        error_detail["message"] = "Authentication required to access this resource."
    elif exc.status_code == 429:
        error_detail["message"] = "Too many requests. Please try again later."
    elif exc.status_code >= 500:
        error_detail["message"] = "Internal server error. Our team has been notified."
    
    logger.warning(
        f"HTTP {exc.status_code} error on {request.method} {request.url.path}: {exc.detail}",
        extra={"status_code": exc.status_code, "detail": str(exc.detail)}
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_detail
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors with detailed field-level feedback"""
    
    validation_errors = []
    for error in exc.errors():
        field_path = " -> ".join(str(x) for x in error["loc"][1:])  # Skip 'body' or 'query'
        validation_errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input")
        })
    
    error_detail = {
        "error_code": "VALIDATION_ERROR",
        "message": "Request validation failed. Please check your input data.",
        "technical_message": "One or more fields contain invalid data",
        "details": {
            "validation_errors": validation_errors,
            "path": str(request.url.path),
            "method": request.method
        },
        "timestamp": datetime.utcnow().isoformat(),
        "support_message": "Please review the field-specific errors and correct your input."
    }
    
    logger.warning(
        f"Validation error on {request.method} {request.url.path}: {len(validation_errors)} field errors",
        extra={"validation_errors": validation_errors}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_detail
    )


async def database_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle database errors with appropriate user messaging"""
    
    error_id = f"DB_ERR_{int(datetime.utcnow().timestamp())}"
    
    # Determine error type and user message
    if isinstance(exc, IntegrityError):
        error_code = "DATA_INTEGRITY_ERROR"
        user_message = "Data integrity constraint violation. Please check your input data."
        technical_message = "Database integrity constraint failed"
    elif isinstance(exc, OperationalError):
        error_code = "DATABASE_UNAVAILABLE"
        user_message = "Database is temporarily unavailable. Please try again later."
        technical_message = "Database operational error"
    else:
        error_code = "DATABASE_ERROR"
        user_message = "Database error occurred. Our team has been notified."
        technical_message = "General database error"
    
    error_detail = {
        "error_code": error_code,
        "message": user_message,
        "technical_message": technical_message,
        "details": {
            "error_id": error_id,
            "error_type": type(exc).__name__,
            "path": str(request.url.path),
            "method": request.method
        },
        "timestamp": datetime.utcnow().isoformat(),
        "support_message": f"Please contact support with error ID: {error_id}"
    }
    
    logger.error(
        f"Database error [{error_id}] on {request.method} {request.url.path}: {str(exc)}",
        extra={"error_id": error_id, "error_type": type(exc).__name__},
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=error_detail
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other unexpected exceptions"""
    
    error_id = f"ERR_{int(datetime.utcnow().timestamp())}"
    
    error_detail = {
        "error_code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred. Our team has been notified.",
        "technical_message": "Internal server error",
        "details": {
            "error_id": error_id,
            "error_type": type(exc).__name__,
            "path": str(request.url.path),
            "method": request.method
        },
        "timestamp": datetime.utcnow().isoformat(),
        "support_message": f"Please contact support with error ID: {error_id}"
    }
    
    logger.exception(
        f"Unexpected error [{error_id}] on {request.method} {request.url.path}: {str(exc)}",
        extra={
            "error_id": error_id, 
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_detail
    )


def setup_error_handlers(app):
    """Register all error handlers with the FastAPI app"""
    
    # Custom Stonks exceptions
    app.add_exception_handler(StonksException, stonks_exception_handler)
    
    # HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    # Database errors
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    
    # Catch-all for unexpected errors
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Error handlers registered successfully")


# Health check for error handling system
def test_error_handlers():
    """Test that error handlers are working correctly"""
    try:
        # Test custom exception
        raise StonksException("Test error", "TEST_ERROR")
    except StonksException as e:
        http_exc = create_http_exception(e)
        assert http_exc.status_code == 500
        assert "TEST_ERROR" in str(http_exc.detail)
        logger.info("Error handler test passed")
        return True
    except Exception as e:
        logger.error(f"Error handler test failed: {e}")
        return False
