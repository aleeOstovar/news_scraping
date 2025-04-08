from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
from datetime import datetime
from app.controllers.scraper_controller import scraper_controller
from app.core.scheduler import scheduler
import logging

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

logger = logging.getLogger(__name__)

@router.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify API connectivity."""
    return {
        "status": "ok",
        "message": "Scraper API is accessible",
        "timestamp": datetime.now().isoformat()
    }

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
        
        # Check if there's a scraping task in progress
        is_scraping = hasattr(scraper_controller, "_scraping_in_progress") and scraper_controller._scraping_in_progress
        
        # Get last run times for each scraper
        last_run_times = {}
        for source_name in scraper_controller.scrapers.keys():
            # Get scraper progress data if available
            progress_data = scraper_controller._scraping_progress.get(source_name, {})
            if progress_data and progress_data.get("end_time"):
                last_run_times[source_name] = progress_data.get("end_time")
            elif hasattr(scraper_controller, "_last_scrape_results") and scraper_controller._last_scrape_results:
                # Fallback to overall last scrape time
                last_run_times[source_name] = scraper_controller._last_scrape_results.get("timestamp")
                
            # Ensure we have end_time for each source that's completed
            if progress_data and progress_data.get("status") == "completed" and not progress_data.get("end_time"):
                # Add end_time if missing but status is completed
                progress_data["end_time"] = datetime.now().isoformat()
                scraper_controller._scraping_progress[source_name] = progress_data
                last_run_times[source_name] = progress_data["end_time"]
        
        return {
            "status": "running" if scheduler_status["is_running"] else "stopped",
            "scheduler": scheduler_status,
            "enabled_sources": list(scraper_controller.scrapers.keys()),
            "last_scrape_results": getattr(scraper_controller, "_last_scrape_results", None),
            "is_scraping": is_scraping,
            "last_run_times": last_run_times
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress")
async def get_scraping_progress() -> Dict[str, Any]:
    """Get the current progress of any ongoing scraping operations."""
    try:
        # Get the current progress
        progress_data = getattr(scraper_controller, "_scraping_progress", None)
        logs = getattr(scraper_controller, "_scraping_logs", [])
        is_scraping = hasattr(scraper_controller, "_scraping_in_progress") and scraper_controller._scraping_in_progress
        
        if not progress_data:
            # No active scraping
            return {
                "is_scraping": is_scraping,
                "total_progress": 100 if not is_scraping else 0,
                "status": "completed" if not is_scraping else "pending",
                "sources": {},
                "logs": logs[-50:] if logs else []  # Return last 50 logs
            }
            
        # Calculate overall progress
        total_sources = len(progress_data.keys())
        if total_sources == 0:
            total_progress = 0
        else:
            # Average progress across all sources
            total_progress = sum(
                source_data.get("progress", 0) 
                for source_data in progress_data.values()
            ) / total_sources
            
        # Determine overall status
        all_completed = all(
            source_data.get("status") == "completed" 
            for source_data in progress_data.values()
        )
        any_error = any(
            source_data.get("status") == "error" 
            for source_data in progress_data.values()
        )
        
        if all_completed:
            status = "completed"
        elif any_error:
            status = "error"
        else:
            status = "running"
            
        return {
            "is_scraping": is_scraping,
            "total_progress": round(total_progress),
            "status": status,
            "sources": progress_data,
            "logs": logs[-50:] if logs else []  # Return last 50 logs
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger")
async def trigger_scraping(source: str = None) -> Dict[str, Any]:
    """Manually trigger scraping for all sources or a specific source."""
    try:
        # Check if scraping is already in progress
        if hasattr(scraper_controller, "_scraping_in_progress") and scraper_controller._scraping_in_progress:
            return {
                "status": "already_running",
                "message": "A scraping process is already in progress. Please wait for it to complete."
            }
        
        # Set scraping in progress flag
        scraper_controller._scraping_in_progress = True
        scraper_controller._scraping_progress = {}
        scraper_controller._scraping_logs = []
        scraper_controller._scraping_start_time = datetime.now()
        
        # Add initial log
        log_message = f"Starting scraping process for {source or 'all sources'}"
        scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
        
        results = {}
        
        if source:
            if source not in scraper_controller.scrapers:
                raise HTTPException(status_code=404, detail=f"Source {source} not found")
            
            # Initialize progress for this source
            scraper_controller._scraping_progress[source] = {
                "status": "running",
                "progress": 0,
                "articles_found": 0,
                "articles_processed": 0,
                "start_time": datetime.now().isoformat(),
                "elapsed_time": "0s"
            }
            
            results = {source: []}
            try:
                articles = scraper_controller.run_scraper(source)
                results[source] = articles if articles else []
                
                # Update progress to completed
                scraper_controller._scraping_progress[source].update({
                    "status": "completed",
                    "progress": 100,
                    "articles_processed": len(results[source]),
                    "end_time": datetime.now().isoformat(),
                })
                
                # Store last run information for persistence
                if not hasattr(scraper_controller, "_last_scrape_results"):
                    scraper_controller._last_scrape_results = {}
                scraper_controller._last_scrape_results = {
                    "timestamp": datetime.now().isoformat(),
                    "source": source,
                    "total_articles": len(articles) if articles else 0
                }
                
                # Send articles to API
                if articles and len(articles) > 0:
                    log_message = f"Processed {len(articles)} articles for {source} - these were sent to API during processing"
                    scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                    
                    # Add API results to the progress data - these are articles that were successfully sent
                    scraper_controller._scraping_progress[source].update({
                        "api_results": {
                            "successful": len(articles),
                            "failed": 0,
                            "total": len(articles)
                        }
                    })
                else:
                    log_message = f"No articles found or processed for {source}"
                    scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                
            except Exception as e:
                results[source] = {"error": str(e)}
                
                # Update progress with error
                scraper_controller._scraping_progress[source].update({
                    "status": "error",
                    "progress": 0,
                    "error": str(e),
                    "end_time": datetime.now().isoformat(),
                })
                
        else:
            # Run all scrapers
            for scraper_name in scraper_controller.scrapers.keys():
                # Initialize progress for this source
                scraper_controller._scraping_progress[scraper_name] = {
                    "status": "running",
                    "progress": 0,
                    "articles_found": 0,
                    "articles_processed": 0,
                    "start_time": datetime.now().isoformat(),
                    "elapsed_time": "0s"
                }
                
                results[scraper_name] = []
                try:
                    log_message = f"Starting scraping for {scraper_name}"
                    scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                    
                    articles = scraper_controller.run_scraper(scraper_name)
                    results[scraper_name] = articles if articles else []
                    
                    # Update progress to completed
                    scraper_controller._scraping_progress[scraper_name].update({
                        "status": "completed",
                        "progress": 100,
                        "articles_processed": len(results[scraper_name]),
                        "end_time": datetime.now().isoformat(),
                    })
                    
                    log_message = f"Completed scraping for {scraper_name}, found {len(results[scraper_name])} articles"
                    scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                    
                    # Send articles to API
                    if results[scraper_name] and len(results[scraper_name]) > 0:
                        log_message = f"Processed {len(results[scraper_name])} articles for {scraper_name} - these were sent to API during processing"
                        scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                        
                        # Add API results to the progress data - these are articles that were successfully sent
                        scraper_controller._scraping_progress[scraper_name].update({
                            "api_results": {
                                "successful": len(results[scraper_name]),
                                "failed": 0,
                                "total": len(results[scraper_name])
                            }
                        })
                    else:
                        log_message = f"No articles found or processed for {scraper_name}"
                        scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                    
                except Exception as e:
                    results[scraper_name] = {"error": str(e)}
                    
                    # Update progress with error
                    scraper_controller._scraping_progress[scraper_name].update({
                        "status": "error",
                        "progress": 0,
                        "error": str(e),
                        "end_time": datetime.now().isoformat(),
                    })
                    
                    log_message = f"Error scraping {scraper_name}: {str(e)}"
                    scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
        
        # Store results for monitoring
        scraper_controller._last_scrape_results = {
            "timestamp": datetime.now().isoformat(),
            "results": results
        }
        
        # Set scraping completed
        scraper_controller._scraping_in_progress = False
        log_message = "Scraping process completed"
        scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
        
        return {
            "status": "success",
            "message": f"Scraping triggered for {'all sources' if not source else source}",
            "results": results,
            "job_id": datetime.now().timestamp()
        }
    except Exception as e:
        # Set scraping not in progress on error
        scraper_controller._scraping_in_progress = False
        log_message = f"Scraping process failed: {str(e)}"
        if hasattr(scraper_controller, "_scraping_logs"):
            scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
        
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_scraping_stats() -> Dict[str, Any]:
    """Get scraping statistics."""
    try:
        # Get last scrape results
        last_results = getattr(scraper_controller, "_last_scrape_results", None)
        
        # Check if we have an API client
        if not hasattr(scraper_controller, "api_client"):
            logger.error("API client not initialized")
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
        
        # Get article counts from API for each source
        sources_stats = {}
        total_articles = 0
        
        for source in scraper_controller.scrapers.keys():
            try:
                # Get article count for this source from the API
                articles_count = 0
                try:
                    # Create URL for source-specific articles count
                    if scraper_controller.api_client:
                        # Make API request to get count
                        api_response = scraper_controller.api_client.session.get(
                            scraper_controller.api_client.build_url(f"/news-posts/count?source={source}"),
                            headers=scraper_controller.api_client.headers
                        )
                        if api_response.status_code == 200:
                            result = api_response.json()
                            articles_count = result.get("count", 0)
                except Exception as count_error:
                    logger.error(f"Error getting article count for {source}: {count_error}")
                
                # Get last run time
                last_run = None
                if hasattr(scraper_controller, "_scraping_progress") and source in scraper_controller._scraping_progress:
                    progress_data = scraper_controller._scraping_progress.get(source, {})
                    if progress_data.get("end_time"):
                        last_run = progress_data.get("end_time")
                
                sources_stats[source] = {
                    "articles_count": articles_count,
                    "last_run": last_run
                }
                
                total_articles += articles_count
            except Exception as source_error:
                logger.error(f"Error getting stats for source {source}: {source_error}")
                sources_stats[source] = {
                    "articles_count": 0,
                    "last_run": None
                }
        
        # Get overall last run time
        last_run = None
        if last_results:
            last_run = last_results.get("timestamp")
        
        return {
            "total_articles": total_articles,
            "sources": sources_stats,
            "last_run": last_run
        }
    except Exception as e:
        logger.error(f"Error getting scraping stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/articles")
async def get_processed_articles() -> Dict[str, Any]:
    """Get information about processed articles from the last scraping run."""
    try:
        last_results = getattr(scraper_controller, "_last_scrape_results", None)
        
        if not last_results:
            return {
                "status": "no_data",
                "message": "No article data available from previous scraping runs"
            }
            
        # Get processed article details
        articles = []
        for source_name, source_articles in last_results.get("results", {}).items():
            for article in source_articles:
                if isinstance(article, dict):
                    articles.append({
                        "title": article.get("title", "Unknown"),
                        "sourceUrl": article.get("sourceUrl", "Unknown"),
                        "source": source_name,
                        "sentToApi": article.get("sent_to_api", False),
                        "processedAt": article.get("processed_at", None)
                    })
        
        return {
            "status": "success",
            "timestamp": last_results.get("timestamp"),
            "totalArticles": len(articles),
            "articles": articles
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error retrieving article data: {str(e)}"
        } 