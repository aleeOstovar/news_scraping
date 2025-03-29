import logging
import re
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup
from persiantools.jdatetime import JalaliDateTime

from app.core.config import PERSIAN_MONTHS
from app.models.article import ArticleLinkModel, ArticleContentModel, ArticleFullModel, ImageModel
from app.scrapers.base_scraper import BaseScraper
from app.services.api_client import APIClient

logger = logging.getLogger(__name__)

class MihanBlockchainScraper(BaseScraper):
    """
    Scraper for MihanBlockchain news website.
    """
    
    def __init__(self, max_age_days: int = 3):
        """
        Initialize the MihanBlockchain scraper.
        
        Args:
            max_age_days: Maximum age of articles to scrape in days
        """
        super().__init__("MihanBlockchain", max_age_days)
        
    def get_article_links(self, url: str) -> List[ArticleLinkModel]:
        """
        Get article links from the MihanBlockchain news page.
        
        Args:
            url: URL of the news page to scrape
            
        Returns:
            List of ArticleLinkModel objects
        """
        result = []
        soup = self.get_soup(url)
        
        if not soup:
            logger.error(f"Failed to fetch and parse URL: {url}")
            return result
            
        # Get current time for age comparison
        current_time = datetime.now(timezone.utc)
        
        # Select the articles using CSS selectors
        articles = soup.select('div.jnews_category_content_wrapper > div.jeg_postblock_4.jeg_postblock > div.jeg_posts.jeg_block_container > div.jeg_posts > article.jeg_post')
        
        # No maximum limit - retrieve all articles from the past 3 days
        logger.info(f"Found {len(articles)} total articles on the page, will collect all within the past 3 days")
        
        # Extract the link and date for each article
        for article in articles:
            try:
                # Extract the link
                link_element = article.select_one('div.jeg_postblock_content > div.jeg_post_meta > div.jeg_meta_date > a')
                if not link_element:
                    continue
                    
                link = link_element['href']
                
                # Extract the date
                date_element = article.select_one('div.jeg_postblock_content > div.jeg_post_meta > div.jeg_meta_date')
                if not date_element:
                    continue
                    
                date_str = date_element.get_text(strip=True)
                
                # Convert Persian date string to Gregorian datetime
                try:
                    # Split the date and time parts
                    persian_date, persian_time = date_str.split(" - ")
                    
                    # Split the Persian date into day, month, and year
                    day, month_name, year = persian_date.split()
                    
                    # Map the Persian month name to the month number
                    month = PERSIAN_MONTHS[month_name]
                    
                    # Convert the Persian date to a format that strptime can parse
                    converted_date = f"{year}-{month:02d}-{int(day):02d}"
                    
                    # Parse the converted date into JalaliDateTime object
                    persian_datetime = JalaliDateTime.strptime(converted_date, '%Y-%m-%d')
        
                    # Add the time information
                    hour, minute = map(int, persian_time.split(":"))
                    persian_datetime = persian_datetime.replace(hour=hour, minute=minute)
        
                    # Convert to Gregorian date
                    gregorian_datetime = persian_datetime.to_gregorian()
        
                    # Convert to UTC
                    utc_datetime = gregorian_datetime.replace(tzinfo=None)
        
                    # Get the date difference
                    time_diff = current_time - utc_datetime.replace(tzinfo=timezone.utc)
        
                    # Only add if within 3 days (can be modified by max_age_days parameter)
                    max_days = min(self.max_age_days, 3)  # Use either max_age_days or 3, whichever is smaller
                    if time_diff <= timedelta(days=max_days):
                        # Format the datetime into a string
                        formatted_date = utc_datetime.strftime('%Y-%m-%d')
        
                        # Append to result
                        result.append(ArticleLinkModel(
                            link=link,
                            date=formatted_date
                        ))
                        
                except Exception as e:
                    logger.error(f"Error converting date {date_str}: {e}")
                    
            except Exception as e:
                logger.error(f"Error processing article: {e}")
        
        logger.info(f"Found {len(result)} articles within the last {min(self.max_age_days, 3)} days")
        
        # Sort articles from oldest to newest for processing
        # This way the newest articles (which come first in the list) will be processed last
        result.sort(key=lambda x: x.date)
        
        return result
        
    def get_article_content(self, url: str, date: str) -> Optional[ArticleContentModel]:
        """
        Get article content from a MihanBlockchain article page.
        
        Args:
            url: URL of the article to scrape
            date: Date of the article
            
        Returns:
            ArticleContentModel object, or None if scraping failed
        """
        soup = self.get_soup(url)
        
        if not soup:
            logger.error(f"Failed to fetch and parse URL: {url}")
            return None
            
        try:
            # Extract the data content, keeping the HTML tags
            data = soup.select_one('div.jeg_inner_content')
            if not data:
                logger.error(f"Could not find content div for article: {url}")
                return None
                
            data_html = data.decode_contents()
    
            # Extract the creator
            creator = soup.select_one('div.jeg_meta_container > div.jeg_post_meta.jeg_post_meta_1 > div.meta_left > div.jeg_meta_author > a')
            creator_name = creator.get_text(strip=True) if creator else "N/A"
    
            # Extract the title
            title = soup.select_one('div.jeg_inner_content > div.entry-header > h1.jeg_post_title')
            title_text = title.get_text(strip=True) if title else "N/A"
    
            # Create and return the model
            return ArticleContentModel(
                link=url,
                date=date,
                data=data_html,
                creator=creator_name,
                title=title_text
            )
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None
            
    def process_article_content(self, article: ArticleContentModel) -> Optional[ArticleFullModel]:
        """
        Process MihanBlockchain article content to extract structured data.
        
        Args:
            article: ArticleContentModel object containing the raw article content
            
        Returns:
            ArticleFullModel object, or None if processing failed
        """
        try:
            html_content = article.data
            if not html_content or html_content == "N/A":
                logger.error(f"No HTML content found for article: {article.link}")
                return None
            
            # Check for placeholders before processing (should be none)
            placeholder_count_before = len(re.findall(r'\*\*IMAGE_PLACEHOLDER_image\d+\*\*', html_content))
            logger.info(f"Before processing: found {placeholder_count_before} placeholders in original HTML")
            
            # Extract thumbnail image
            thumbnail_image = self.extract_thumbnail_image(html_content)
            logger.info(f"Extracted thumbnail image: {thumbnail_image}")
            
            # Extract and process images
            html_with_placeholders, images = self.extract_and_replace_images(html_content)
            
            # Check for placeholders after processing
            placeholder_count_after = len(re.findall(r'\*\*IMAGE_PLACEHOLDER_image\d+\*\*', html_with_placeholders))
            logger.info(f"After processing: found {placeholder_count_after} placeholders in modified HTML")
            
            # Extract content
            content = self.extract_content(html_with_placeholders)
            
            # Use the title from the article model
            title = article.title
            
            # Extract tags
            tags = self.extract_tags(html_content)
            
            # Get image URLs
            image_urls = [img.url for img in images]
            
            # Add thumbnail if present and not already in images
            if thumbnail_image and thumbnail_image not in image_urls:
                image_urls.insert(0, thumbnail_image)
                
            # Create article data
            article_data = ArticleFullModel(
                title=title,
                source="MihanBlockchain",
                sourceUrl=article.link,
                publishDate=article.date,
                creator=article.creator,
                content=content,
                tags=tags,
                imagesUrl=image_urls
            )
            
            return article_data
                
        except Exception as e:
            logger.error(f"Error processing article content for {article.link}: {e}")
            return None
            
    def extract_thumbnail_image(self, html: str) -> Optional[str]:
        """
        Extract the thumbnail image from the article HTML.
        
        Args:
            html: HTML content of the article
            
        Returns:
            URL of the thumbnail image, or None if not found
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Look for the thumbnail image
        try:
            # First try to find the featured image
            featured_img = soup.select_one('div.jeg_featured')
            if featured_img:
                img_tag = featured_img.select_one('img')
                if img_tag and 'src' in img_tag.attrs:
                    return img_tag['src']
            
            # If not found, try to find any image in the article
            article_img = soup.select_one('img')
            if article_img and 'src' in article_img.attrs:
                return article_img['src']
                
        except Exception as e:
            logger.error(f"Error extracting thumbnail image: {e}")
            
        return None
        
    def extract_and_replace_images(self, html: str) -> Tuple[str, List[ImageModel]]:
        """
        Extract images from the article HTML and replace them with placeholders.
        
        Args:
            html: HTML content of the article
            
        Returns:
            Tuple containing the HTML with placeholders and list of image models
        """
        soup = BeautifulSoup(html, 'html.parser')
        images = []
        
        # Find all image elements in the content
        try:
            # Replace each image with a placeholder
            for i, img in enumerate(soup.select('img')):
                if 'src' in img.attrs:
                    # Create an image model
                    image_model = ImageModel(
                        id=f"image{i+1}",
                        url=img['src'],
                        caption=img.get('alt', '') or img.get('title', '')
                    )
                    
                    # Replace the image with a placeholder in the HTML
                    placeholder_text = f"**IMAGE_PLACEHOLDER_image{i+1}**"
                    placeholder_tag = soup.new_tag('p')
                    placeholder_tag.string = placeholder_text
                    img.replace_with(placeholder_tag)
                    
                    # Add to the list of images
                    images.append(image_model)
                    
            # Return the modified HTML and images
            return str(soup), images
            
        except Exception as e:
            logger.error(f"Error extracting images: {e}")
            return html, images

    def extract_content(self, html: str) -> List[str]:
        """
        Extract content paragraphs from the article HTML.
        
        Args:
            html: HTML content with image placeholders
            
        Returns:
            List of content paragraphs
        """
        soup = BeautifulSoup(html, 'html.parser')
        content_elements = []
        
        # Select the content container
        content_container = soup.select_one('div.content-inner')
        
        # If the specific container isn't found, use the full HTML
        if not content_container:
            content_container = soup
        
        # Extract all paragraph elements, headings, and placeholders
        try:
            elements = content_container.select('p, h1, h2, h3, h4, h5, h6, blockquote, ul, ol')
            
            # These classes indicate elements that should be excluded
            excluded_classes = [
                'jeg_post_meta',
                'jeg_share_button',
                'jeg_meta_container',
                'jeg_bottombar',
                'jeg_header',
                'jeg_footer',
                'jeg_ad',
                'jeg_authorbox'
            ]
            
            for element in elements:
                # Skip empty paragraphs
                if not element.text.strip() and "**IMAGE_PLACEHOLDER_" not in element.text:
                    continue
                
                # Skip elements with excluded classes
                if any(excluded_class in element.get('class', []) for excluded_class in excluded_classes):
                    continue
                    
                # Check if the element is a parent of excluded elements
                if element.select_one(', '.join(f'.{cls}' for cls in excluded_classes)):
                    continue
                
                # Check if element is in an excluded container - commenting out as is_in_excluded_container is not used
                # element_position = html.find(str(element))
                # if element_position != -1 and self.is_in_excluded_container(html, element_position):
                #     continue
                
                # Extract text content
                text = element.get_text(strip=True)
                
                # Special handling for image placeholders
                if element.name == 'p' and "**IMAGE_PLACEHOLDER_" in element.text:
                    text = element.text.strip()
                
                # Add to content if not empty
                if text:
                    content_elements.append(text)
            
            # Special processing for image placeholders in paragraphs
            for i, content in enumerate(content_elements):
                if "**IMAGE_PLACEHOLDER_" in content:
                    # Extract just the placeholder part
                    match = re.search(r'(\*\*IMAGE_PLACEHOLDER_image\d+\*\*)', content)
                    if match:
                        placeholder = match.group(1)
                        # Replace the content with just the placeholder
                        content_elements[i] = placeholder
            
            # Remove duplicates while preserving order
            unique_elements = []
            seen = set()
            for element in content_elements:
                if element not in seen:
                    unique_elements.append(element)
                    seen.add(element)
                    
            return unique_elements
            
        except Exception as e:
            logger.error(f"Error extracting content: {e}")
            return ["Content extraction failed"]
            
    def extract_tags(self, html: str) -> List[str]:
        """
        Extract tags from the article HTML.
        
        Args:
            html: HTML content of the article
            
        Returns:
            List of tags
        """
        soup = BeautifulSoup(html, 'html.parser')
        tags = []
        
        try:
            # Look for tags container
            tag_container = soup.select_one('div.jeg_post_tags')
            if tag_container:
                # Extract all tag links
                tag_links = tag_container.select('a')
                for tag_link in tag_links:
                    tag_text = tag_link.get_text(strip=True)
                    if tag_text and tag_text not in tags:
                        tags.append(tag_text)
                        
            # Limit to a maximum of 10 tags
            if len(tags) > 10:
                tags = tags[:10]
                
            return tags
            
        except Exception as e:
            logger.error(f"Error extracting tags: {e}")
            return []
    
    # The following functions appear to be unused in the actual scraping process and can be commented out

    # def is_in_excluded_container(self, html: str, element_position: int) -> bool:
    #     """
    #     Check if the element position is within an excluded container.
    #     
    #     Args:
    #         html: HTML content of the article
    #         element_position: Position of the element in the HTML
    #         
    #     Returns:
    #         True if in excluded container, False otherwise
    #     """
    #     # Get a sample of the text around the match for context
    #     start_pos = max(0, element_position - 500)
    #     end_pos = min(len(html), element_position + 500)
    #     context = html[start_pos:end_pos]
    #     
    #     # Check if the element is within any excluded containers
    #     excluded_container_patterns = [
    #         r'<div\s+class="jeg_post_meta">.*?</div>',  # Metadata section
    #         r'<div\s+class="jeg_share_button">.*?</div>',  # Share buttons
    #         r'<div\s+class="jeg_authorbox">.*?</div>',  # Author information
    #         r'<div\s+class="jeg_navigation\s+jeg_pagination">.*?</div>',  # Pagination
    #         r'<div\s+class="jeg_bottombar">.*?</div>',  # Bottom bar
    #         r'<footer\s+class="jeg_footer">.*?</footer>',  # Footer
    #         r'<header\s+class="jeg_header">.*?</header>',  # Header
    #         r'<div\s+class="jeg_ad">.*?</div>',  # Advertisements
    #         r'<div\s+class="jeg_meta_container">.*?</div>'  # Metadata container
    #     ]
    #     
    #     # Check if the element is within any of the excluded containers
    #     for pattern in excluded_container_patterns:
    #         # Find all matches of the pattern in the context
    #         matches = re.finditer(pattern, context, re.DOTALL)
    #         for match in matches:
    #             # Calculate global position of the match in the original HTML
    #             global_start = start_pos + match.start()
    #             global_end = start_pos + match.end()
    #             
    #             # Check if the element position is within this match
    #             if global_start <= element_position <= global_end:
    #                 return True
    #                 
    #     return False

    # def scrape_articles(self, base_url: str) -> List[ArticleFullModel]:
    #     """
    #     Scrape articles from MihanBlockchain website.
    #     
    #     Args:
    #         base_url: Base URL of the website
    #         
    #     Returns:
    #         List of processed articles
    #     """
    #     articles = []
    #     
    #     # Get article links
    #     article_links = self.get_article_links(base_url)
    #     logger.info(f"Found {len(article_links)} article links")
    #     
    #     # Process each article
    #     for i, article_link in enumerate(article_links):
    #         logger.info(f"Processing article {i+1}/{len(article_links)}: {article_link.link}")
    #         
    #         # Get article content
    #         content = self.get_article_content(article_link.link, article_link.date)
    #         if not content:
    #             logger.warning(f"Failed to get content for article: {article_link.link}")
    #             continue
    #             
    #         # Process article content
    #         processed = self.process_article_content(content)
    #         if not processed:
    #             logger.warning(f"Failed to process content for article: {article_link.link}")
    #             continue
    #             
    #         # Add to list of articles
    #         articles.append(processed)
    #         
    #     return articles 