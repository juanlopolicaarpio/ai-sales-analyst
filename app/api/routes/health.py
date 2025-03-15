from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
import time

from app.config import settings
from app.db.database import get_async_db
from app.utils.logger import logger

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_async_db)):
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns:
        dict: Health status information
    """
    start_time = time.time()
    
    # Check database connection
    db_status = {"status": "ok", "latency_ms": 0}
    try:
        # Test query to check database connection
        result = await db.execute(text("SELECT 1"))
        await result.fetchone()
        db_status["latency_ms"] = int((time.time() - start_time) * 1000)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = {"status": "error", "message": str(e)}
    
    # Overall health status
    health_status = "ok" if db_status["status"] == "ok" else "error"
    
    # Calculate total response time
    total_latency_ms = int((time.time() - start_time) * 1000)
    
    return {
        "status": health_status,
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "timestamp": int(time.time()),
        "latency_ms": total_latency_ms,
        "components": {
            "database": db_status
        }
    }


@router.get("/ping")
async def ping():
    """
    Simple ping endpoint for basic connectivity checks.
    
    Returns:
        dict: Simple ping response
    """
    return {"status": "ok", "message": "pong"}