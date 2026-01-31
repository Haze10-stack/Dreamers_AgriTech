"""
Farm AI Assistant - Main Application

FastAPI application for multi-agent farming assistant
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

# Import database
from models.database import engine, Base, init_db

# Import routes
from api.routes import router

# Import config
from config.settings import settings


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for the application
    """
    # Startup
    print("🌱 Starting Farm AI Assistant API...")
    print(f"📍 Environment: {settings.ENVIRONMENT}")
    print(f"🔑 Groq Model: {settings.GROQ_MODEL}")
    
    # Initialize database
    print("🗄️  Initializing database...")
    init_db()
    print("✅ Database initialized")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Farm AI Assistant API...")


# Create FastAPI app
app = FastAPI(
    title="Farm AI Assistant API",
    description="Multi-agent AI system for farming assistance (Pre-sowing → Growth → Harvest)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """
    Add processing time to response headers
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """
    Handle 404 errors
    """
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Resource not found",
            "path": str(request.url.path)
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """
    Handle 500 errors
    """
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "message": "Something went wrong. Please try again later."
        }
    )


# ============================================================================
# ROUTES
# ============================================================================

# Include API routes
app.include_router(router, prefix="/api")


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint - API information
    """
    return {
        "service": "Farm AI Assistant API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "features": [
            "Multi-agent crop planning (AutoGen + Groq)",
            "Pre-sowing crop recommendations",
            "Growth monitoring (greenhouse + traditional)",
            "Harvest guidance and market analysis",
            "Feedback loop for plan adaptation",
            "Weather and market data integration"
        ],
        "endpoints": {
            "auth": "/api/auth/*",
            "chat": "/api/chat",
            "crops": "/api/crop/*",
            "tasks": "/api/tasks/*",
            "greenhouse": "/api/greenhouse/*",
            "observations": "/api/observations/*",
            "weather": "/api/weather/{location}",
            "market": "/api/market/*"
        }
    }


@app.get("/health")
async def health():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "service": "Farm AI Assistant API",
        "database": "connected" if engine else "disconnected"
    }


# ============================================================================
# STARTUP MESSAGE
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                  ║
    ║           🌾 FARM AI ASSISTANT API 🌾                            ║
    ║                                                                  ║
    ║  Multi-Agent Farming Assistant                                  ║
    ║  Powered by AutoGen + Groq (Llama 3.3 70B)                      ║
    ║                                                                  ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )