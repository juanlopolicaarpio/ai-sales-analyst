import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.database import get_async_db, Base, engine
from app.api.routes import slack, whatsapp, email, health, auth, stores, preferences, shopify_auth
from app.utils.logger import logger

# Startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app."""
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} environment")

    # Create database tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    logger.info(f"Shutting down {settings.APP_NAME}")


# Create the FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="AI Sales Analyst for E-commerce",
    version="1.0.0",
    lifespan=lifespan
)

# ✅ Unified CORS middleware (no conditionals)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://0.0.0.0:8080",
        settings.APP_URL,
    ],
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
    max_age=600,
)

# Middleware to add request ID and log timing
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    logger.info(f"Request {request_id}: {request.method} {request.url.path}")
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-ID"] = request_id

    logger.info(f"Response {request_id}: {response.status_code} in {process_time:.3f}s")

    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
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
    return {"message": f"Welcome to {settings.APP_NAME} API"}


# Serve static files if present
if os.path.exists("./static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


# Run with Uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
