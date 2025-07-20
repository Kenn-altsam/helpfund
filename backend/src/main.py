"""
Ayala Foundation Backend API

Main FastAPI application entry point for the Ayala Foundation backend.
This service helps charity funds discover companies and sponsorship opportunities.
"""

import os
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from dotenv import load_dotenv

from .ai_conversation.router import router as ai_conversation_router
from .companies.router import router as companies_router
from .auth.router import router as auth_router
from .funds.router import router as funds_router
from .chats.router import router as chats_router
from .core.config import get_settings

# Load environment variables
load_dotenv()

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Ayala Foundation Backend API",
    description="Backend service for charity funds to discover companies and sponsorship opportunities",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=ORJSONResponse,
)

@app.on_event("startup")
def on_startup():
    """Synchronous startup event handler."""
    print("🚀 [STARTUP] Ayala Foundation Backend API starting up")
    print("📋 [STARTUP] Available endpoints:")
    print("   • POST /api/v1/ai/chat-assistant - AI Chat Assistant")
    print("   • POST /api/v1/ai/charity-research - Company Charity Research")
    print("   • /api/v1/auth/* - Authentication endpoints")
    print("   • /api/v1/companies/* - Company search endpoints")
    print("   • /api/v1/funds/* - Fund management endpoints")
    print("✅ [STARTUP] Database schema is managed by Alembic")
    
    # Apply database optimizations automatically on startup
    try:
        from .core.database import engine
        from .core.database_config import optimize_database_connection
        print("🔧 [STARTUP] Applying database optimizations...")
        optimize_database_connection(engine)
        print("✅ [STARTUP] Database optimizations completed")
    except Exception as e:
        print(f"⚠️ [STARTUP] Database optimization failed (non-critical): {e}")
        print("⚠️ [STARTUP] Database will still work, but may not be fully optimized")

@app.on_event("shutdown")
def on_shutdown():
    """Synchronous shutdown event handler."""
    print("🛑 [SHUTDOWN] Ayala Foundation Backend API shutting down gracefully")

# Configure CORS for mobile development
# Very permissive settings to ensure iPhone/Android apps can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=settings.ALLOW_METHODS,
    allow_headers=settings.ALLOW_HEADERS,
    expose_headers=["*"],  # Allow all response headers to be accessible
)

# Include routers
# Main endpoints:
# - /api/v1/auth/* - Authentication endpoints
# - /api/v1/funds/* - Fund profile management and main chat endpoint
# - /api/v1/ai/* - Advanced AI assistant endpoints
# - /api/v1/companies/* - Company search and data endpoints
app.include_router(auth_router, prefix="/api/v1")
app.include_router(funds_router, prefix="/api/v1")
app.include_router(ai_conversation_router, prefix="/api/v1")
app.include_router(companies_router, prefix="/api/v1")
app.include_router(chats_router, prefix="/api/v1")

@app.get("/")
def root():
    """Root endpoint - API health check"""
    print("🏠 [ROOT] Root endpoint accessed")
    return {
        "status": "success",
        "message": "Ayala Foundation Backend API is running",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    print("❤️ [HEALTH] Health check endpoint accessed")
    
    # Check critical services
    health_status = "success"
    health_message = "API is healthy"
    health_data = {
        "service": "ayala-foundation-backend",
        "version": "1.0.0",
        "checks": {}
    }
    
    # Check database connection
    try:
        from .core.database import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        health_data["checks"]["database"] = "healthy"
    except Exception as e:
        health_data["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status = "warning"
        health_message = "API is running but some services are degraded"
    
    # Check environment variables
    required_env_vars = ["DATABASE_URL", "SECRET_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        health_data["checks"]["environment"] = f"missing: {', '.join(missing_vars)}"
        health_status = "warning"
        health_message = "API is running but some configuration is missing"
    else:
        health_data["checks"]["environment"] = "healthy"
    
    return {
        "status": health_status,
        "message": health_message,
        "data": health_data
    }

@app.get("/network-test")
def network_test():
    """Network connectivity test endpoint for mobile debugging"""
    print("🌐 [NETWORK] Network test endpoint accessed - checking mobile connectivity")
    return {
        "status": "success",
        "message": "Network connection working!",
        "timestamp": "2025-01-03T10:00:00Z",
        "data": {
            "cors_enabled": True,
            "mobile_friendly": True,
            "server_info": {
                "host": settings.host,
                "port": settings.port,
                "allowed_origins": settings.allowed_origins
            }
        }
    }

@app.get("/test")
def simple_test():
    """Simple test endpoint for iOS app connectivity"""
    print("📱 [TEST] Simple test endpoint accessed - iOS app connectivity check")
    return {
        "message": "Backend is working!",
        "server_ip": "192.168.58.253",
        "port": 8000,
        "timestamp": "2025-01-03T10:00:00Z"
    } 