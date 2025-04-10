import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse

from app.config import settings
from app.db.database import get_async_db, Base, engine
from app.api.routes import slack, whatsapp, email, health, auth, stores, preferences, shopify_auth
from app.utils.logger import logger
from app.api.middleware.security import get_current_user
from app.api.middleware.error_handler import error_handler

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

# CORS middleware configuration - all allowed headers and methods
# CORS middleware with specific origins instead of wildcard
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        settings.FRONTEND_URL,
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
        "X-Request-ID",
        "Cache-Control"
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
    return await error_handler(request, exc)


# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(slack.router, prefix="/api", tags=["Slack"])
app.include_router(whatsapp.router, prefix="/api", tags=["WhatsApp"])
app.include_router(email.router, prefix="/api", tags=["Email"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(stores.router, prefix="/api", tags=["Stores"])
app.include_router(preferences.router, prefix="/api", tags=["User Preferences"])
app.include_router(shopify_auth.router, prefix="/api", tags=["Shopify Integration"])

# Create static directory if it doesn't exist
static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

# Add a specific route for the debug HTML
@app.get("/shopify_debug.html", response_class=HTMLResponse)
async def get_shopify_debug_html():
    debug_file = static_dir / "shopify_debug.html"
    if not debug_file.exists():
        debug_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Shopify Connection Debugger</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #2c3e50; }
        .card { background-color: #fff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1); padding: 20px; margin-bottom: 20px; }
        input[type="text"] { width: 100%; padding: 8px; margin-bottom: 10px; }
        button { background-color: #4f46e5; color: white; border: none; padding: 10px 15px; border-radius: 4px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>Shopify Connection Debugger</h1>
    
    <div class="card">
        <h2>Connect to Shopify</h2>
        <input type="text" id="shop-url" placeholder="your-store.myshopify.com" />
        <button onclick="connectToShopify()">Connect to Shopify</button>
    </div>
    
    <script>
        function connectToShopify() {
            const shopUrl = document.getElementById('shop-url').value.trim();
            
            if (!shopUrl) {
                alert('Please enter a Shopify store URL');
                return;
            }
            
            // Clean up the URL
            let cleanShopUrl = shopUrl.replace(/^https?:\/\//, '');
            if (!cleanShopUrl.includes('.')) {
                cleanShopUrl = `${cleanShopUrl}.myshopify.com`;
            }
            
            // Redirect to the debug endpoint
            window.location.href = `/api/shopify/auth/debug?shop=${encodeURIComponent(cleanShopUrl)}`;
        }
    </script>
</body>
</html>"""
        # Write the debug HTML file
        with open(debug_file, "w") as f:
            f.write(debug_content)
    
    # Read and return the file content
    with open(debug_file, "r") as f:
        content = f.read()
    return HTMLResponse(content=content)

# Test endpoint to verify authentication
@app.get("/api/auth-test")
async def auth_test(current_user = Depends(get_current_user)):
    """Test endpoint to verify authentication."""
    return {"status": "authenticated", "user_id": str(current_user.id)}

# Root endpoint
@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME} API"}


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Also mount at root for backward compatibility
if os.path.exists("./static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static_root")


# Run with Uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )