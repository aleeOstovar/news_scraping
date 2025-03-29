import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.core.config import get_settings, NEWS_SOURCES, SCHEDULER_INTERVAL_HOURS
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
        self._scraping_progress = {}
        self._scraping_logs = []
        
        # Initialize scrapers for enabled news sources
        self._initialize_scrapers()
        
        # The _processed_urls field is unused, can be removed
        # self._processed_urls = set()
        
    def _initialize_scrapers(self):
        """Initialize scrapers for all enabled news sources."""
        # Initialize MihanBlockchain scraper if enabled
        if NEWS_SOURCES["mihan_blockchain"]["enabled"]:
            # Initialize progress tracking
            self._scraping_progress["mihan_blockchain"] = {
                "status": "idle",
                "progress": 0,
                "articles_found": 0,
                "articles_processed": 0
            }
            
            # Initialize the scraper
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
            
            # Run the scraper - this will only collect articles but not send them to the API
            # The base_scraper.run method returns a list of processed article dictionaries
            collected_articles = scraper.run(source_url)
            
            # We'll track which articles were successfully sent to the API
            successful_articles = []
            
            # Process each article immediately and individually
            for idx, article in enumerate(collected_articles):
                try:
                    title = article.get('title', 'Unknown')
                    source_url = article.get('sourceUrl', 'Unknown')
                    
                    logger.info(f"Sending article {idx+1}/{len(collected_articles)}: '{title}' - {source_url}")
                    
                    # Add log entry to scraping logs if available
                    if hasattr(self, "_scraping_logs"):
                        log_message = f"Sending article to API: '{title}' ({source_url})"
                        self._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                        
                    # Send the article (only once, right here)
                    response = self.api_client.post_news_data(article)
                    
                    # Log success with response details
                    logger.info(f"Successfully sent article: '{title}' - Response: {response}")
                    
                    # Add to successful articles list
                    successful_articles.append(article)
                    
                    # Add success log entry
                    if hasattr(self, "_scraping_logs"):
                        log_message = f"✅ ARTICLE POSTED SUCCESSFULLY: '{title}' ({source_url})"
                        self._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                        
                except Exception as e:
                    title = article.get('title', 'Unknown')
                    source_url = article.get('sourceUrl', 'Unknown')
                    
                    logger.error(f"Failed to send article {idx+1}/{len(collected_articles)} - '{title}' ({source_url}): {str(e)}")
                    
                    # Add failure log entry with detailed error
                    if hasattr(self, "_scraping_logs"):
                        log_message = f"❌ ARTICLE POST FAILED: '{title}' ({source_url}) - Error: {str(e)}"
                        self._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
            
            logger.info(f"Scraper for {source_name} completed. Processed and sent {len(successful_articles)} articles out of {len(collected_articles)} collected.")
            
            # Return only the successfully sent articles
            return successful_articles
        except Exception as e:
            logger.error(f"Error running scraper for {source_name}: {e}")
            return []
            
    def run_all_scrapers(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Run all enabled scrapers.
        
        Returns:
            Dictionary mapping source names to lists of scraped articles that were successfully saved
        """
        results = {}
        total_articles = 0
        
        # Reset progress tracking
        for source_name in self.scrapers:
            self._scraping_progress[source_name] = {
                "status": "running",
                "progress": 0,
                "start_time": datetime.now().isoformat(),
                "articles_found": 0,
                "articles_processed": 0
            }
        
        # Reset logs
        self._scraping_logs = []
        self._scraping_logs.append(f"[{datetime.now().isoformat()}] Starting scraping for all enabled sources")
        
        for source_name in self.scrapers:
            try:
                logger.info(f"Running scraper for {source_name}")
                self._scraping_logs.append(f"[{datetime.now().isoformat()}] Starting scraper for {source_name}")
                
                # Run the scraper (which now processes and saves articles one by one)
                articles = self.run_scraper(source_name)
                results[source_name] = articles
                
                # Count total articles for summary
                if articles and len(articles) > 0:
                    total_articles += len(articles)
                    
                self._scraping_logs.append(f"[{datetime.now().isoformat()}] Completed scraper for {source_name}, found and saved {len(articles)} articles")
            except Exception as e:
                logger.error(f"Error running scraper for {source_name}: {e}")
                results[source_name] = []
                
                self._scraping_logs.append(f"[{datetime.now().isoformat()}] Error running scraper for {source_name}: {e}")
                
                # Update progress to show error status
                self._scraping_progress[source_name]["status"] = "error"
                self._scraping_progress[source_name]["error"] = str(e)
        
        # Log summary of the entire run
        logger.info(f"Run completed for all scrapers. Total articles processed and saved: {total_articles}")
        self._scraping_logs.append(f"[{datetime.now().isoformat()}] All scrapers completed. Total articles processed and saved: {total_articles}")
        
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

# Create a singleton instance
scraper_controller = ScraperController() 