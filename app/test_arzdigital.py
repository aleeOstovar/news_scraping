import logging
import json
from app.scrapers.arzdigital import ArzDigitalScraper
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Run a test of the ArzDigital scraper."""
    logger.info("Starting ArzDigital scraper test")
    
    # Initialize the scraper
    scraper = ArzDigitalScraper(max_age_days=3)
    
    # Get URL from settings
    url = settings.NEWS_SOURCES["arzdigital"]["url"]
    logger.info(f"Using URL: {url}")
    
    # Get article links
    article_links = scraper.get_article_links(url)
    logger.info(f"Found {len(article_links)} article links")
    
    # Limit to 3 articles for testing
    article_links = article_links[:3]
    logger.info(f"Processing first 3 articles")
    
    articles = []
    
    # Process each article
    for i, article_link in enumerate(article_links):
        logger.info(f"Processing article {i+1}/{len(article_links)}: {article_link.link}")
        
        # Get article content
        content = scraper.get_article_content(article_link.link, article_link.date)
        if not content:
            logger.warning(f"Failed to get content for article: {article_link.link}")
            continue
            
        # Process article content
        processed = scraper.process_article_content(content)
        if not processed:
            logger.warning(f"Failed to process content for article: {article_link.link}")
            continue
            
        # Convert to dict
        article_dict = processed.dict()
        articles.append(article_dict)
        
        # Print article info
        logger.info(f"Article {i+1}: {article_dict['title']} - {article_dict['sourceUrl']}")
    
    # Print json output
    print(json.dumps(articles, ensure_ascii=False, indent=2))
    logger.info(f"Successfully processed {len(articles)} articles")

if __name__ == "__main__":
    main() 