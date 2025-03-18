from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
from datetime import datetime
from app.controllers.scraper_controller import scraper_controller
from app.core.scheduler import scheduler

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

@router.get("/status")
async def get_scraper_status() -> Dict[str, Any]:
    """Get the current status of the scraper service."""
    try:
        # Get scheduler status
        scheduler_status = {
            "is_running": scheduler.scheduler.running,
            "next_run": None,
            "last_run": None
        }
        
        # Get next scheduled job
        jobs = scheduler.scheduler.get_jobs()
        if jobs:
            next_job = min(jobs, key=lambda x: x.next_run_time if x.next_run_time else datetime.max)
            if next_job.next_run_time:
                scheduler_status["next_run"] = next_job.next_run_time.isoformat()
        
        # Get last run time from logs (you might want to implement a proper logging system)
        # This is a placeholder
        scheduler_status["last_run"] = datetime.now().isoformat()
        
        return {
            "status": "running" if scheduler_status["is_running"] else "stopped",
            "scheduler": scheduler_status,
            "enabled_sources": list(scraper_controller.scrapers.keys()),
            "last_scrape_results": getattr(scraper_controller, "_last_scrape_results", None)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger")
async def trigger_scraping(source: str = None) -> Dict[str, Any]:
    """Manually trigger scraping for all sources or a specific source."""
    try:
        results = {}
        
        if source:
            if source not in scraper_controller.scrapers:
                raise HTTPException(status_code=404, detail=f"Source {source} not found")
            
            results = {source: []}
            try:
                articles = scraper_controller.run_scraper(source)
                results[source] = articles if articles else []
            except Exception as e:
                results[source] = {"error": str(e)}
        else:
            # Run all scrapers
            for scraper_name in scraper_controller.scrapers.keys():
                results[scraper_name] = []
                try:
                    articles = scraper_controller.run_scraper(scraper_name)
                    results[scraper_name] = articles if articles else []
                except Exception as e:
                    results[scraper_name] = {"error": str(e)}
        
        # Store results for monitoring
        scraper_controller._last_scrape_results = {
            "timestamp": datetime.now().isoformat(),
            "results": results
        }
        
        return {
            "status": "success",
            "message": f"Scraping triggered for {'all sources' if not source else source}",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_scraping_stats() -> Dict[str, Any]:
    """Get scraping statistics."""
    try:
        # Get last scrape results
        last_results = getattr(scraper_controller, "_last_scrape_results", None)
        
        if not last_results:
            # Initialize with empty data if no previous scraping has occurred
            return {
                "total_articles": 0,
                "sources": {
                    source: {
                        "articles_count": 0,
                        "last_run": None
                    } for source in scraper_controller.scrapers.keys()
                },
                "last_run": None
            }
        
        # Calculate statistics
        total_articles = sum(len(articles) if articles else 0 for articles in last_results.get("results", {}).values())
        
        # Per-source statistics
        sources_stats = {}
        for source in scraper_controller.scrapers.keys():
            articles = last_results.get("results", {}).get(source, [])
            sources_stats[source] = {
                "articles_count": len(articles) if articles else 0,
                "last_run": last_results.get("timestamp")
            }
        
        return {
            "total_articles": total_articles,
            "sources": sources_stats,
            "last_run": last_results.get("timestamp")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 