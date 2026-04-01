"""
Application middleware for logging, error handling, and request tracking.
"""
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests for tracking."""
    
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class ExecutionTimeMiddleware(BaseHTTPMiddleware):
    """Track and log request execution time."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        execution_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(execution_time)
        
        # Log slow requests
        if execution_time > 1.0:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {execution_time:.2f}s"
            )
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Centralized error handling middleware."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(
                f"Request error: {request.method} {request.url.path} - {str(exc)}",
                exc_info=True
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "request_id": getattr(request.state, "request_id", "unknown"),
                },
            )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all API requests and responses."""
    
    async def dispatch(self, request: Request, call_next):
        # Log request
        logger.info(
            f"→ {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )
        
        response = await call_next(request)
        
        # Log response
        logger.info(
            f"← {request.method} {request.url.path} "
            f"status={response.status_code}"
        )
        
        return response
