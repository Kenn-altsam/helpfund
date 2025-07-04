"""
Ayala Foundation Backend API

Main FastAPI application entry point for the Ayala Foundation backend.
This service helps charity funds discover companies and sponsorship opportunities.
"""

import os
from typing import List
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .ai_conversation.router import router as ai_conversation_router
from .companies.router import router as companies_router
from .auth.router import router as auth_router
from .funds.router import router as funds_router
from .core.config import get_settings
from .core.database import init_database

# Load environment variables
load_dotenv()

# Get settings
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan"""
    print("✅ Ayala Foundation Backend API starting up")
    # Initialize database tables
    init_database()
    print("✅ Database initialized")
    yield
    print("✅ Ayala Foundation Backend API shutting down")

# Create FastAPI app
app = FastAPI(
    title="Ayala Foundation Backend API",
    description="Backend service for charity funds to discover companies and sponsorship opportunities",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS for mobile development
# Very permissive settings to ensure iPhone/Android apps can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=settings.allow_credentials,
    allow_methods=settings.allow_methods,
    allow_headers=settings.allow_headers,
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

@app.get("/")
async def root():
    """Root endpoint - API health check"""
    return {
        "status": "success",
        "message": "Ayala Foundation Backend API is running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "success",
        "message": "API is healthy",
        "data": {
            "service": "ayala-foundation-backend",
            "version": "1.0.0"
        }
    }

@app.get("/network-test")
async def network_test():
    """Network connectivity test endpoint for mobile debugging"""
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
async def simple_test():
    """Simple test endpoint for iOS app connectivity"""
    return {
        "message": "Backend is working!",
        "server_ip": "192.168.58.253",
        "port": 8000,
        "timestamp": "2025-01-03T10:00:00Z"
    } 