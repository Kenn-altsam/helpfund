#!/usr/bin/env python3
"""
Ayala Foundation Backend - Development Server

Simple script to run the FastAPI development server.
"""

import os
import sys
import uvicorn

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

if __name__ == "__main__":
    # Run the FastAPI development server
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )