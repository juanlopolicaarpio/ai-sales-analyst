from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from jose.exceptions import JWTError
import traceback

from app.utils.logger import logger

async def error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global error handler for all exceptions"""
    error_response = {
        "detail": "Internal server error"
    }
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    
    # Get the exception class name for logging
    error_class = exc.__class__.__name__
    
    # Get the error location for easier debugging
    error_location = f"{request.method} {request.url.path}"
    
    # Handle different types of exceptions
    if isinstance(exc, RequestValidationError):
        # Handle validation errors
        error_response = {
            "detail": "Validation error",
            "errors": exc.errors()
        }
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        logger.warning(f"Validation error in {error_location}: {exc.errors()}")
    
    elif isinstance(exc, JWTError):
        # Handle JWT errors
        error_response = {
            "detail": "Authentication error"
        }
        status_code = status.HTTP_401_UNAUTHORIZED
        logger.warning(f"JWT error in {error_location}: {str(exc)}")
    
    elif isinstance(exc, SQLAlchemyError):
        # Handle database errors
        error_response = {
            "detail": "Database error"
        }
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(f"Database error in {error_location}: {str(exc)}")
    
    else:
        # Handle other exceptions
        logger.error(f"Unhandled exception in {error_location}: {error_class} - {str(exc)}")
        logger.error(traceback.format_exc())
    
    # Add request_id if available in request state
    if hasattr(request.state, "request_id"):
        error_response["request_id"] = request.state.request_id
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )