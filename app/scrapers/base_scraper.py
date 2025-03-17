import logging
import time
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from app.config import USER_AGENT, ARTICLE_DELAY_SECONDS
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
        logger.info(f"Starting scraper for {self.source_name} at {source_url}")
        
        # Get article links
        article_links = self.get_article_links(source_url)
        logger.info(f"Found {len(article_links)} article links")
        
        # Process articles
        processed_articles = []
        
        for i, article_link in enumerate(article_links):
            url = article_link.link
            date = article_link.date
            
            # Check if article already exists
            if self.api_client.check_article_exists(url):
                logger.info(f"Article {i+1}/{len(article_links)} already exists: {url}")
                continue
                
            logger.info(f"Processing article {i+1}/{len(article_links)}: {url}")
            
            # Get article content
            content = self.get_article_content(url, date)
            if not content:
                logger.warning(f"Failed to get content for article: {url}")
                continue
                
            # Process article content
            processed = self.process_article_content(content)
            if not processed:
                logger.warning(f"Failed to process content for article: {url}")
                continue
                
            # Add processed article to results
            processed_dict = processed.dict()
            processed_articles.append(processed_dict)
            
            # Add delay between articles
            if i < len(article_links) - 1:
                logger.info(f"Waiting {ARTICLE_DELAY_SECONDS} seconds before next article...")
                time.sleep(ARTICLE_DELAY_SECONDS)
                
        logger.info(f"Scraper for {self.source_name} completed. Processed {len(processed_articles)} articles")
        return processed_articles 