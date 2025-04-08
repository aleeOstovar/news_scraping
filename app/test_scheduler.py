import time
import logging
from datetime import datetime
from app.core.scheduler import scheduler
from app.controllers.scraper_controller import scraper_controller
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Run a test of the scheduler."""
    logger.info("Starting scheduler test")
    
    # Remove any existing job
    scheduler.remove_job("all_scrapers")
    
    # Schedule the job to run every 1 minute for testing
    job_id = scheduler.add_interval_job(
        func=scraper_controller.run_all_scrapers,
        hours=1/60,  # 1 minute
        job_id="all_scrapers",
        start_now=True
    )
    
    logger.info(f"Scheduled scrapers to run every 1 minute (job_id: {job_id})")
    
    # Wait for a few minutes to see multiple runs
    wait_time = 5 * 60  # 5 minutes
    logger.info(f"Waiting for {wait_time} seconds to observe multiple runs...")
    
    try:
        for i in range(wait_time):
            if i % 30 == 0:  # Log every 30 seconds
                now = datetime.now()
                logger.info(f"Still waiting... ({i}/{wait_time} seconds elapsed)")
                
                # Get job info
                jobs = scheduler.scheduler.get_jobs()
                for job in jobs:
                    next_run = job.next_run_time
                    if next_run:
                        time_diff = next_run - now
                        logger.info(f"Job {job.id} next run in {time_diff.total_seconds()} seconds")
                    else:
                        logger.warning(f"Job {job.id} has no next_run_time (is paused)")
            
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    
    logger.info("Test completed")

if __name__ == "__main__":
    main() 