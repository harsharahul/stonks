"""
Enhanced Exception Handling for Stonks Platform

Custom exceptions with user-friendly messages and proper error codes.
Provides consistent error handling across the application.
"""

from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)


class StonksException(Exception):
    """Base exception for all Stonks-specific errors"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "STONKS_ERROR",
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.user_message = user_message or message
        super().__init__(self.message)


class DataNotFoundException(StonksException):
    """Raised when requested data is not found"""
    
    def __init__(
        self, 
        resource_type: str, 
        identifier: str,
        user_message: Optional[str] = None
    ):
        message = f"{resource_type} with identifier '{identifier}' not found"
        user_msg = user_message or f"The requested {resource_type.lower()} was not found"
        super().__init__(
            message=message,
            error_code="DATA_NOT_FOUND",
            details={"resource_type": resource_type, "identifier": identifier},
            user_message=user_msg
        )


class ValidationException(StonksException):
    """Raised when input validation fails"""
    
    def __init__(
        self, 
        field_name: str, 
        field_value: Any, 
        validation_rule: str,
        user_message: Optional[str] = None
    ):
        message = f"Validation failed for field '{field_name}': {validation_rule}"
        user_msg = user_message or f"Invalid value for {field_name}: {validation_rule}"
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={
                "field_name": field_name, 
                "field_value": str(field_value), 
                "validation_rule": validation_rule
            },
            user_message=user_msg
        )


class WebSocketException(StonksException):
    """Raised when WebSocket operations fail"""
    
    def __init__(
        self, 
        operation: str, 
        reason: str,
        user_message: Optional[str] = None
    ):
        message = f"WebSocket {operation} failed: {reason}"
        user_msg = user_message or f"Real-time connection issue: {reason}"
        super().__init__(
            message=message,
            error_code="WEBSOCKET_ERROR",
            details={"operation": operation, "reason": reason},
            user_message=user_msg
        )


class AlertGenerationException(StonksException):
    """Raised when alert generation fails"""
    
    def __init__(
        self, 
        ticker: str, 
        alert_type: str, 
        reason: str,
        user_message: Optional[str] = None
    ):
        message = f"Failed to generate {alert_type} alert for {ticker}: {reason}"
        user_msg = user_message or f"Unable to create alert for {ticker}. Please try again later."
        super().__init__(
            message=message,
            error_code="ALERT_GENERATION_ERROR",
            details={"ticker": ticker, "alert_type": alert_type, "reason": reason},
            user_message=user_msg
        )


class SignalProcessingException(StonksException):
    """Raised when signal processing fails"""
    
    def __init__(
        self, 
        ticker: str, 
        signal_type: str, 
        reason: str,
        user_message: Optional[str] = None
    ):
        message = f"Failed to process {signal_type} signal for {ticker}: {reason}"
        user_msg = user_message or f"Unable to process market signal for {ticker}. Data may be temporarily unavailable."
        super().__init__(
            message=message,
            error_code="SIGNAL_PROCESSING_ERROR",
            details={"ticker": ticker, "signal_type": signal_type, "reason": reason},
            user_message=user_msg
        )


class RateLimitException(StonksException):
    """Raised when rate limits are exceeded"""
    
    def __init__(
        self, 
        limit_type: str, 
        reset_time: Optional[int] = None,
        user_message: Optional[str] = None
    ):
        message = f"Rate limit exceeded for {limit_type}"
        user_msg = user_message or f"Too many requests. Please try again in a few moments."
        if reset_time:
            user_msg += f" Limit resets in {reset_time} seconds."
        
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"limit_type": limit_type, "reset_time": reset_time},
            user_message=user_msg
        )


class DatabaseException(StonksException):
    """Raised when database operations fail"""
    
    def __init__(
        self, 
        operation: str, 
        error: Exception,
        user_message: Optional[str] = None
    ):
        message = f"Database {operation} failed: {str(error)}"
        user_msg = user_message or "Database temporarily unavailable. Please try again later."
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details={"operation": operation, "original_error": str(error)},
            user_message=user_msg
        )


class ExternalServiceException(StonksException):
    """Raised when external service calls fail"""
    
    def __init__(
        self, 
        service_name: str, 
        operation: str, 
        error: Exception,
        user_message: Optional[str] = None
    ):
        message = f"{service_name} {operation} failed: {str(error)}"
        user_msg = user_message or f"{service_name} service is temporarily unavailable. Please try again later."
        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service_name": service_name, "operation": operation, "original_error": str(error)},
            user_message=user_msg
        )


def create_http_exception(
    exception: StonksException,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
) -> HTTPException:
    """Convert a StonksException to an HTTPException with proper formatting"""
    
    # Map error codes to appropriate HTTP status codes
    status_code_mapping = {
        "DATA_NOT_FOUND": status.HTTP_404_NOT_FOUND,
        "VALIDATION_ERROR": status.HTTP_400_BAD_REQUEST,
        "RATE_LIMIT_EXCEEDED": status.HTTP_429_TOO_MANY_REQUESTS,
        "WEBSOCKET_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "ALERT_GENERATION_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "SIGNAL_PROCESSING_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "DATABASE_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
        "EXTERNAL_SERVICE_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
    }
    
    mapped_status_code = status_code_mapping.get(exception.error_code, status_code)
    
    # Create detailed error response
    error_detail = {
        "error_code": exception.error_code,
        "message": exception.user_message,
        "technical_message": exception.message,
        "details": exception.details,
        "timestamp": datetime.utcnow().isoformat(),
        "support_message": "If this issue persists, please contact support with the error code."
    }
    
    # Log the technical error for debugging
    logger.error(
        f"API Error [{exception.error_code}]: {exception.message}",
        extra={"details": exception.details, "user_message": exception.user_message}
    )
    
    return HTTPException(
        status_code=mapped_status_code,
        detail=error_detail
    )


def handle_unexpected_error(error: Exception, operation: str) -> HTTPException:
    """Handle unexpected errors with proper logging and user messaging"""
    
    error_id = f"ERR_{int(datetime.utcnow().timestamp())}"
    
    logger.exception(
        f"Unexpected error in {operation} [ID: {error_id}]: {str(error)}",
        extra={"operation": operation, "error_id": error_id}
    )
    
    error_detail = {
        "error_code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred. Our team has been notified.",
        "technical_message": f"Internal server error in {operation}",
        "details": {"error_id": error_id, "operation": operation},
        "timestamp": datetime.utcnow().isoformat(),
        "support_message": f"Please contact support with error ID: {error_id}"
    }
    
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=error_detail
    )


def safe_operation(operation_name: str):
    """Decorator to safely handle operations with proper error handling"""
    
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except StonksException as e:
                raise create_http_exception(e)
            except Exception as e:
                raise handle_unexpected_error(e, operation_name)
        
        return wrapper
    return decorator


# Error message templates for common scenarios
ERROR_MESSAGES = {
    "ticker_not_found": "The stock ticker '{ticker}' was not found in our database. Please check the symbol and try again.",
    "date_invalid": "The date '{date}' is not valid. Please use YYYY-MM-DD format.",
    "date_future": "Future dates are not supported. Please select a date up to today.",
    "no_data_available": "No data is available for {ticker} on {date}. This may be due to market holidays or data processing delays.",
    "connection_failed": "Unable to connect to real-time data feed. Please check your internet connection and try again.",
    "calculation_failed": "Feature calculation failed for {ticker}. This may be due to insufficient market data.",
    "alert_cooldown": "An alert for {ticker} was recently sent. Next alert available in {time_remaining}.",
    "service_unavailable": "The {service} service is temporarily unavailable. Please try again in a few minutes.",
    "rate_limit": "You've exceeded the rate limit for {operation}. Please wait {wait_time} before trying again."
}


def get_user_friendly_message(error_type: str, **kwargs) -> str:
    """Get a user-friendly error message with proper formatting"""
    
    template = ERROR_MESSAGES.get(error_type, "An error occurred: {error}")
    try:
        return template.format(**kwargs)
    except KeyError as e:
        logger.warning(f"Missing parameter {e} for error message template {error_type}")
        return "An unexpected error occurred. Please try again later."
