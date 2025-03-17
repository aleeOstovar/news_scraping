from typing import Dict, List, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.controllers.scraper_controller import scraper_controller
from app.core.scheduler import scheduler

router = APIRouter(prefix="/api/v1", tags=["scraper"])

@router.get("/status")
async def get_status():
    """Get the status of the scraper service."""
    return {"status": "running"}

@router.post("/scrape")
async def scrape_all(background_tasks: BackgroundTasks):
    """
    Trigger a scraping job for all enabled news sources.
    
    The job runs in the background, so this endpoint returns immediately.
    
    Returns:
        JSON response with a message indicating that the job was started
    """
    # Run the scrapers in a background task
    background_tasks.add_task(scraper_controller.run_all_scrapers)
    
    return {"message": "Scraping job started in background"}

@router.post("/scrape/{source_name}")
async def scrape_source(source_name: str, background_tasks: BackgroundTasks):
    """
    Trigger a scraping job for a specific news source.
    
    Args:
        source_name: Name of the news source to scrape
        
    Returns:
        JSON response with a message indicating that the job was started
    """
    # Check if the source exists
    if source_name not in scraper_controller.scrapers:
        raise HTTPException(status_code=404, detail=f"Scraper for {source_name} not found")
    
    # Run the scraper in a background task
    background_tasks.add_task(scraper_controller.run_scraper, source_name)
    
    return {"message": f"Scraping job for {source_name} started in background"}

@router.get("/scheduler/jobs")
async def get_scheduler_jobs():
    """
    Get a list of all scheduled jobs.
    
    Returns:
        List of job information
    """
    jobs = scheduler.scheduler.get_jobs()
    
    job_info = []
    for job in jobs:
        job_info.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })
        
    return job_info

@router.post("/scheduler/start")
async def start_scheduler():
    """
    Start the scheduler.
    
    Returns:
        JSON response with a message indicating that the scheduler was started
    """
    scraper_controller.schedule_scrapers(start_now=True)
    return {"message": "Scheduler started"}

@router.post("/scheduler/stop/{job_id}")
async def stop_scheduler_job(job_id: str):
    """
    Stop a scheduled job.
    
    Args:
        job_id: ID of the job to stop
        
    Returns:
        JSON response with a message indicating whether the job was stopped
    """
    success = scheduler.remove_job(job_id)
    
    if success:
        return {"message": f"Job {job_id} stopped"}
    else:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found") 