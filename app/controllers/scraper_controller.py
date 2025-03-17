import logging
import time
from typing import Dict, List, Any, Optional

from app.config import NEWS_SOURCES, SCHEDULER_INTERVAL_HOURS
from app.core.scheduler import scheduler
from app.scrapers.mihan_blockchain import MihanBlockchainScraper
from app.services.api_client import APIClient

logger = logging.getLogger(__name__)

class ScraperController:
    """
    Controller for managing multiple scrapers.
    
    This class is responsible for initializing and running scrapers for
    different news sources, and managing the workflow of the scraping process.
    """
    
    def __init__(self):
        """Initialize the scraper controller."""
        self.api_client = APIClient()
        self.scrapers = {}
        self._initialize_scrapers()
        
    def _initialize_scrapers(self):
        """Initialize scrapers for all enabled news sources."""
        # Initialize MihanBlockchain scraper if enabled
        if NEWS_SOURCES["mihan_blockchain"]["enabled"]:
            self.scrapers["mihan_blockchain"] = MihanBlockchainScraper(
                max_age_days=NEWS_SOURCES["mihan_blockchain"]["max_age_days"]
            )
            logger.info("Initialized MihanBlockchain scraper")
            
        # Add more scrapers for other news sources here
        
        logger.info(f"Initialized {len(self.scrapers)} scrapers")
        
    def run_scraper(self, source_name: str) -> List[Dict[str, Any]]:
        """
        Run a specific scraper.
        
        Args:
            source_name: Name of the news source to scrape
            
        Returns:
            List of scraped articles
        """
        if source_name not in self.scrapers:
            logger.error(f"Scraper for {source_name} not found")
            return []
            
        scraper = self.scrapers[source_name]
        source_url = NEWS_SOURCES[source_name]["url"]
        
        try:
            logger.info(f"Running scraper for {source_name}")
            result = scraper.run(source_url)
            logger.info(f"Scraper for {source_name} completed, found {len(result)} articles")
            return result
        except Exception as e:
            logger.error(f"Error running scraper for {source_name}: {e}")
            return []
    
    def run_all_scrapers(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run all enabled scrapers.
        
        Returns:
            Dictionary mapping source names to lists of scraped articles
        """
        results = {}
        
        for source_name in self.scrapers:
            results[source_name] = self.run_scraper(source_name)
            
        return results
    
    def schedule_scrapers(self, start_now: bool = False):
        """
        Schedule all scrapers to run periodically.
        
        Args:
            start_now: Whether to run the scrapers immediately
        """
        job_id = scheduler.add_interval_job(
            func=self.run_all_scrapers,
            hours=SCHEDULER_INTERVAL_HOURS,
            job_id="all_scrapers",
            start_now=start_now
        )
        
        logger.info(f"Scheduled all scrapers to run every {SCHEDULER_INTERVAL_HOURS} hours (job_id: {job_id})")
        
    def send_articles_to_api(self, articles: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Send articles to the API.
        
        Args:
            articles: List of articles to send
            
        Returns:
            Dictionary with statistics about the operation
        """
        successful_count = 0
        failed_count = 0
        
        for idx, article in enumerate(articles):
            try:
                logger.info(f"Sending article {idx+1}/{len(articles)}: {article.get('title', 'Unknown')}")
                self.api_client.post_news_data(article)
                logger.info(f"Successfully sent article: {article.get('title', 'Unknown')}")
                successful_count += 1
            except Exception as e:
                logger.error(f"Failed to send article {idx+1}: {str(e)}")
                failed_count += 1
                
        return {
            "successful": successful_count,
            "failed": failed_count,
            "total": len(articles)
        }

# Create a singleton instance
scraper_controller = ScraperController() 