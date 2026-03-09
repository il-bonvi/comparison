"""
COMPARISON - FastAPI application for FIT trace comparison
Standalone app for overlaying and comparing two cycling FIT files
"""

import logging
from typing import Dict, Any

from fastapi import FastAPI

# Import router
from routes.comparison import router as comparison_router, setup_comparison_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# FASTAPI APPLICATION INITIALIZATION
# ============================================================================

app = FastAPI(
    title="FIT Comparison Tool",
    description="Compare two cycling FIT files with interactive 3D map visualization",
    version="1.0.0"
)

# Session storage
sessions: Dict[str, Dict[str, Any]] = {}

logger.info("Initializing Comparison Application...")

# Setup router
logger.info("Setting up comparison router...")
setup_comparison_router(sessions)

# Register router
logger.info("Registering routes...")
app.include_router(comparison_router, tags=["comparison"])

logger.info("Comparison Application initialized successfully!")
logger.info("Available endpoints:")
logger.info("  GET  /                     - Main comparison page")
logger.info("  POST /api/upload           - Upload two FIT files")


# ============================================================================
# STARTUP/SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Called when application starts"""
    logger.info("Comparison app started on http://localhost:8000")


@app.on_event("shutdown")
async def shutdown_event():
    """Called when application shuts down"""
    logger.info("Comparison app shut down")


# ============================================================================
# MAIN - Run with Uvicorn
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
