import logging
import time
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from app.core.config import USER_AGENT, ARTICLE_DELAY_SECONDS
from app.models.article import ArticleLinkModel, ArticleContentModel, ArticleFullModel
from app.services.api_client import APIClient

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """
    Abstract base class for all scrapers.
    
    All site-specific scrapers should inherit from this class and implement
    the abstract methods to handle site-specific scraping logic.
    """
    
    def __init__(self, source_name: str, max_age_days: int = 8):
        """
        Initialize the base scraper.
        
        Args:
            source_name: Name of the news source
            max_age_days: Maximum age of articles to scrape in days
        """
        self.source_name = source_name
        self.max_age_days = max_age_days
        self.headers = {"User-Agent": USER_AGENT}
        self.api_client = APIClient()
        logger.info(f"Initialized {source_name} scraper")
        
    def get_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL.
        
        Args:
            url: URL to fetch HTML from
            
        Returns:
            HTML content as string, or None if request failed
        """
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching URL {url}: {str(e)}")
            return None
            
    def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch and parse HTML content from a URL.
        
        Args:
            url: URL to fetch HTML from
            
        Returns:
            BeautifulSoup object, or None if request failed
        """
        html = self.get_html(url)
        if html:
            return BeautifulSoup(html, 'html.parser')
        return None
        
    @abstractmethod
    def get_article_links(self, url: str) -> List[ArticleLinkModel]:
        """
        Get article links from the news page.
        
        Args:
            url: URL of the news page to scrape
            
        Returns:
            List of ArticleLinkModel objects
        """
        pass
        
    @abstractmethod
    def get_article_content(self, url: str, date: str) -> Optional[ArticleContentModel]:
        """
        Get article content from an article page.
        
        Args:
            url: URL of the article to scrape
            date: Date of the article
            
        Returns:
            ArticleContentModel object, or None if scraping failed
        """
        pass
        
    @abstractmethod
    def process_article_content(self, article: ArticleContentModel) -> Optional[ArticleFullModel]:
        """
        Process article content to extract structured data.
        
        Args:
            article: ArticleContentModel object containing the raw article content
            
        Returns:
            ArticleFullModel object, or None if processing failed
        """
        pass
        
    def run(self, source_url: str) -> List[Dict[str, Any]]:
        """
        Run the scraper on the given source URL.
        
        Args:
            source_url: URL of the news page to scrape
            
        Returns:
            List of processed articles
        """
        from app.controllers.scraper_controller import scraper_controller
        start_time = datetime.now()
        
        # Hard limit on number of articles to process
        max_processed_articles = 10
        
        logger.info(f"Starting scraper for {self.source_name} at {source_url}")
        
        # Get article links
        article_links = self.get_article_links(source_url)
        logger.info(f"Found {len(article_links)} article links, max to process: {max_processed_articles}")
        
        # Hard limit on the number of articles to process
        if len(article_links) > max_processed_articles:
            logger.info(f"Limiting article links to {max_processed_articles} (was {len(article_links)})")
            article_links = article_links[:max_processed_articles]
        
        # Update progress - after finding links
        if hasattr(scraper_controller, "_scraping_progress") and self.source_name in scraper_controller._scraping_progress:
            scraper_controller._scraping_progress[self.source_name].update({
                "articles_found": len(article_links),
                "progress": 10,  # 10% complete after finding links
                "elapsed_time": str(datetime.now() - start_time).split('.')[0]  # Remove microseconds
            })
            log_message = f"Found {len(article_links)} articles to process for {self.source_name}"
            if hasattr(scraper_controller, "_scraping_logs"):
                scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
        
        # Process articles
        processed_articles = []
        
        # Keep track of processed URLs in this run to avoid duplicates
        processed_urls = set()
        
        # Count articles checked against API
        articles_existing_in_api = 0
        
        for i, article_link in enumerate(article_links):
            url = article_link.link
            date = article_link.date
            
            # Skip if this URL was already processed in this run
            if url in processed_urls:
                logger.info(f"Skipping article {i+1}/{len(article_links)}: {url} (already processed in this run)")
                continue
            
            # Add to processed URLs set for this run
            processed_urls.add(url)
            
            # Update progress for article processing
            progress_percentage = 10 + int((i / len(article_links)) * 90) if len(article_links) > 0 else 100
            if hasattr(scraper_controller, "_scraping_progress") and self.source_name in scraper_controller._scraping_progress:
                scraper_controller._scraping_progress[self.source_name].update({
                    "progress": progress_percentage,
                    "articles_processed": len(processed_articles),
                    "current_article": url,
                    "elapsed_time": str(datetime.now() - start_time).split('.')[0]  # Remove microseconds
                })
            
            # Check if article already exists in the API database
            try:
                if self.api_client.check_article_exists(url):
                    articles_existing_in_api += 1
                    logger.info(f"Article {i+1}/{len(article_links)} already exists in API: {url}")
                    
                    # Log skipped article
                    if hasattr(scraper_controller, "_scraping_logs"):
                        log_message = f"Skipping article {i+1}/{len(article_links)} (already exists in API): {url}"
                        scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                    
                    # If we've found 10 articles already exist, we can stop processing
                    # This helps avoid processing a large number of duplicate articles
                    if articles_existing_in_api >= 5:
                        logger.info(f"Found {articles_existing_in_api} articles that already exist in API. Stopping processing.")
                        if hasattr(scraper_controller, "_scraping_logs"):
                            log_message = f"Found {articles_existing_in_api} articles that already exist in API. Stopping processing to avoid duplicates."
                            scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                        break
                    
                    continue
            except Exception as e:
                logger.error(f"Error checking if article exists ({url}): {e}")
                # Continue processing the article even if check fails
            
            logger.info(f"Processing article {i+1}/{len(article_links)}: {url}")
            
            # Log current article processing
            if hasattr(scraper_controller, "_scraping_logs"):
                log_message = f"Processing article {i+1}/{len(article_links)}: {url}"
                scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
            
            # Get article content
            content = self.get_article_content(url, date)
            if not content:
                logger.warning(f"Failed to get content for article: {url}")
                
                # Log failure
                if hasattr(scraper_controller, "_scraping_logs"):
                    log_message = f"Failed to get content for article: {url}"
                    scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                
                continue
                
            # Process article content
            processed = self.process_article_content(content)
            if not processed:
                logger.warning(f"Failed to process content for article: {url}")
                
                # Log failure
                if hasattr(scraper_controller, "_scraping_logs"):
                    log_message = f"Failed to process content for article: {url}"
                    scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                
                continue
                
            # Add processed article to results
            try:
                processed_dict = processed.dict()
                
                # Validate required fields
                if not processed_dict.get('title'):
                    logger.error(f"Missing title in processed article: {url}")
                    continue
                    
                if not processed_dict.get('content') or not isinstance(processed_dict.get('content'), list) or len(processed_dict.get('content')) == 0:
                    logger.error(f"Missing or invalid content in processed article: {url}")
                    continue
                    
                # Ensure imagesUrl is a list
                if processed_dict.get('imagesUrl') is None:
                    processed_dict['imagesUrl'] = []
                
                # Add processing timestamp
                processed_dict['processed_at'] = datetime.now().isoformat()
                    
                # Log successful article processing
                logger.info(f"Successfully processed article: {processed_dict.get('title')} - Content paragraphs: {len(processed_dict.get('content', []))}, Images: {len(processed_dict.get('imagesUrl', []))}")
                
                # Add article to the results (don't send to API here - the controller will do it)
                processed_articles.append(processed_dict)
                
                # Log success
                if hasattr(scraper_controller, "_scraping_logs"):
                    log_message = f"Successfully processed article: {processed_dict.get('title')} ({url})"
                    scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
            except Exception as e:
                logger.error(f"Error converting processed article to dict ({url}): {e}")
                
                # Log failure
                if hasattr(scraper_controller, "_scraping_logs"):
                    log_message = f"Error preparing article for API: {e}"
                    scraper_controller._scraping_logs.append(f"[{datetime.now().isoformat()}] {log_message}")
                
                continue
            
            # Add delay between articles
            if i < len(article_links) - 1:
                logger.info(f"Waiting {ARTICLE_DELAY_SECONDS} seconds before next article...")
                time.sleep(ARTICLE_DELAY_SECONDS)
                
        # Update final progress
        if hasattr(scraper_controller, "_scraping_progress") and self.source_name in scraper_controller._scraping_progress:
            scraper_controller._scraping_progress[self.source_name].update({
                "progress": 100,
                "status": "completed",
                "articles_processed": len(processed_articles),
                "end_time": datetime.now().isoformat(),
                "elapsed_time": str(datetime.now() - start_time).split('.')[0]  # Remove microseconds
            })
        
        logger.info(f"Scraper for {self.source_name} completed. Processed {len(processed_articles)} articles")
        return processed_articles 