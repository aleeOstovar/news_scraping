import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers.api import router as api_router
from app.controllers.scraper_controller import scraper_controller
from app.core.scheduler import scheduler
from app.routers import monitoring

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="News Scraper API",
    description="API for scraping news websites",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)
app.include_router(monitoring.router)

@app.on_event("startup")
async def startup_event():
    """Initialize services when the application starts."""
    logger.info("Starting up application...")
    
    # Initialize the scraper controller - this line is redundant as controller is already initialized
    # scraper_controller._initialize_scrapers()
    
    # Start the scheduler if auto-start is enabled
    if settings.SCHEDULER_AUTO_START:
        logger.info("Auto-starting scheduler...")
        scraper_controller.schedule_scrapers()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources when the application shuts down."""
    logger.info("Shutting down application...")
    
    # Shutdown the scheduler
    scheduler.shutdown()

@app.get("/")
async def root():
    """Root endpoint returning basic information about the API."""
    return {
        "name": "News Scraper API",
        "version": "1.0.0",
        "status": "running"
    } 