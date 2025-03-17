import logging
from datetime import datetime
from typing import Callable, List, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

logger = logging.getLogger(__name__)

class ScraperScheduler:
    """
    A scheduler for managing scraper jobs.
    Uses APScheduler to run jobs at specified intervals.
    """
    def __init__(self):
        """Initialize the scheduler."""
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("Scheduler initialized")
        
    def add_interval_job(
        self, 
        func: Callable, 
        hours: int = 2, 
        job_id: Optional[str] = None,
        args: Optional[List] = None, 
        kwargs: Optional[dict] = None,
        start_now: bool = False
    ) -> str:
        """
        Add a job to be run at regular intervals.
        
        Args:
            func: Function to be executed
            hours: Interval in hours between job runs
            job_id: Unique identifier for the job
            args: List of positional arguments to pass to the function
            kwargs: Dictionary of keyword arguments to pass to the function
            start_now: Whether to run the job immediately
            
        Returns:
            The job ID
        """
        if job_id is None:
            job_id = f"job_{datetime.now().timestamp()}"
            
        self.scheduler.add_job(
            func=func,
            trigger=IntervalTrigger(hours=hours),
            id=job_id,
            args=args or [],
            kwargs=kwargs or {},
            next_run_time=datetime.now() if start_now else None
        )
        
        logger.info(f"Added interval job '{job_id}' to run every {hours} hours")
        return job_id
    
    def add_cron_job(
        self, 
        func: Callable, 
        hour: str = "*/2", 
        job_id: Optional[str] = None,
        args: Optional[List] = None, 
        kwargs: Optional[dict] = None
    ) -> str:
        """
        Add a job to be run according to a cron schedule.
        
        Args:
            func: Function to be executed
            hour: Cron expression for the hour (default: every 2 hours)
            job_id: Unique identifier for the job
            args: List of positional arguments to pass to the function
            kwargs: Dictionary of keyword arguments to pass to the function
            
        Returns:
            The job ID
        """
        if job_id is None:
            job_id = f"cron_{datetime.now().timestamp()}"
            
        self.scheduler.add_job(
            func=func,
            trigger=CronTrigger(hour=hour),
            id=job_id,
            args=args or [],
            kwargs=kwargs or {}
        )
        
        logger.info(f"Added cron job '{job_id}' with schedule hour='{hour}'")
        return job_id
    
    def remove_job(self, job_id: str) -> bool:
        """
        Remove a job from the scheduler.
        
        Args:
            job_id: The ID of the job to remove
            
        Returns:
            True if the job was removed, False otherwise
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job '{job_id}'")
            return True
        except JobLookupError:
            logger.warning(f"Failed to remove job '{job_id}': Job not found")
            return False
    
    def shutdown(self):
        """Shut down the scheduler."""
        self.scheduler.shutdown()
        logger.info("Scheduler shut down")
        
# Create a singleton instance
scheduler = ScraperScheduler() 