#!/usr/bin/env python
"""
News Scraper Application Entry Point
"""
import os
import sys
import logging
import argparse
import uvicorn

# Add parent directory to path to allow imports
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.core.config import get_settings

# Parse command line arguments
parser = argparse.ArgumentParser(description="News Scraper Application")
parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to run the API server on")
parser.add_argument("--port", type=int, default=8000, help="Port to run the API server on")
parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
parser.add_argument("--log-level", type=str, default=None, help="Logging level (DEBUG, INFO, WARNING, ERROR)")
args = parser.parse_args()

# Configure logging
settings = get_settings()
log_level = args.log_level if args.log_level else settings.LOG_LEVEL
log_format = settings.LOG_FORMAT

logging.basicConfig(
    level=log_level,
    format=log_format
)

logger = logging.getLogger(__name__)
logger.info(f"Starting News Scraper API on {args.host}:{args.port}")

if __name__ == "__main__":
    # Run the API server
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
        log_level=log_level.lower(),
    ) 