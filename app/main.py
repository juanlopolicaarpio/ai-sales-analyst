import os
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import time
from contextlib import asynccontextmanager

from app.config import settings
from app.db.database import get_async_db, Base, engine
from app.api.routes import slack, whatsapp, email, health
from app.utils.logger import logger
from app.api.routes import auth, stores, preferences, shopify_auth

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI app.
    
    This function handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} environment")
    
    # Create database tables if they don't exist
    async with engine.begin() as conn:
        # This is only for development - in production use Alembic migrations
        if settings.APP_ENV == "development":
            # await conn.run_sync(Base.metadata.drop_all)  # Uncomment to reset DB
            await conn.run_sync(Base.metadata.create_all)
    
    # Yield control to FastAPI
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")


# Create the FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="AI Sales Analyst for E-commerce",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware with expanded and properly configured allowed origins
origins = [
    # Allow requests from frontend URL configured in settings
    settings.FRONTEND_URL,
    
    # Common development URLs - add any others your team might use
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://0.0.0.0:8080",
    
    # If using other ports or development servers, add them here
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    
    # Add your production URLs here (without the protocol prefix)
    # "https://your-production-domain.com",
]

# For development environments, allow any origin for easier testing
# In production, this should be set to False and use a specific list of origins
if settings.APP_ENV == "development" and settings.DEBUG:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins in development
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods
        allow_headers=["*"],  # Allow all headers
        expose_headers=["*"],  # Expose all headers
    )
else:
    # More restrictive CORS for production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=[
            "Authorization", 
            "Content-Type", 
            "Accept", 
            "Origin", 
            "User-Agent",
            "X-Requested-With",
            "X-Request-ID"
        ],
        expose_headers=[
            "X-Process-Time", 
            "X-Request-ID"
        ],
        max_age=600,  # Cache preflight requests for 10 minutes
    )

# Add request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add a unique ID to each request for tracing."""
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Log request details
    logger.info(f"Request {request_id}: {request.method} {request.url.path}")
    
    # Time the request processing
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Add timing headers
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-ID"] = request_id
    
    # Log response details
    logger.info(f"Response {request_id}: {response.status_code} in {process_time:.3f}s")
    
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle exceptions globally and return a standard error response."""
    logger.exception(f"Unhandled exception in {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(slack.router, prefix="/api", tags=["Slack"])
app.include_router(whatsapp.router, prefix="/api", tags=["WhatsApp"])
app.include_router(email.router, prefix="/api", tags=["Email"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(stores.router, prefix="/api", tags=["Stores"])
app.include_router(preferences.router, prefix="/api", tags=["User Preferences"])
app.include_router(shopify_auth.router, prefix="/api", tags=["Shopify Integration"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": f"Welcome to {settings.APP_NAME} API"}


# Mount static files for the frontend
# This assumes your frontend build output is in a 'static' directory
# For production, you might want to use a dedicated web server instead
if os.path.exists("./static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


# Run the application with Uvicorn if this file is executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )