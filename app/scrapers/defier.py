import logging
import re
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup
from persiantools.jdatetime import JalaliDateTime

from app.core.config import settings
from app.models.article import ArticleLinkModel, ArticleContentModel, ArticleFullModel, ImageModel
from app.scrapers.base_scraper import BaseScraper
from app.services.api_client import APIClient

logger = logging.getLogger(__name__)

class DefierScraper(BaseScraper):
    """
    Scraper for Defier news website.
    """
    
    def __init__(self, api_client=None, max_age_days: int = 3):
        """
        Initialize the Defier scraper.
        
        Args:
            api_client: API client for sending data
            max_age_days: Maximum age of articles to scrape in days
        """
        super().__init__("Defier", max_age_days)
        if api_client:
            self.api_client = api_client
        
    def get_article_links(self, url: str) -> List[ArticleLinkModel]:
        """
        Get article links from the Defier news page.
        """
        result = []
        soup = self.get_soup(url)

        if not soup:
            logger.error(f"Failed to fetch and parse URL: {url}")
            return result

        current_time = datetime.now(timezone.utc)

        # Find article elements on the page
        articles = soup.select('article')

        logger.info(f"Found {len(articles)} total articles on the page, will collect all within the past {self.max_age_days} days")

        for article in articles:
            try:
                # Extract the link
                link_element = article.find('a')
                if not link_element or not link_element.has_attr('href'):
                    continue

                link = link_element['href'].strip()
                
                # Extract the date
                date_element = article.select_one('time')
                if not date_element:
                    continue

                # The date format is Persian like "۱۸ فروردین ۱۴۰۴"
                date_text = date_element.get_text(strip=True)
                
                try:
                    # Parse Persian date
                    # Expected format: "۱۸ فروردین ۱۴۰۴"
                    parts = date_text.split()
                    if len(parts) != 3:
                        logger.warning(f"Unexpected date format: {date_text}")
                        continue
                        
                    # Convert Persian digits to English
                    day = self._convert_persian_numbers(parts[0])
                    month_name = parts[1]
                    year = self._convert_persian_numbers(parts[2])
                    
                    # Map Persian month name to month number
                    if month_name not in settings.PERSIAN_MONTHS:
                        logger.warning(f"Unknown Persian month: {month_name}")
                        continue
                        
                    month = settings.PERSIAN_MONTHS[month_name]
                    
                    # Create JalaliDateTime and convert to Gregorian
                    jalali_date = JalaliDateTime(int(year), month, int(day))
                    gregorian_date = jalali_date.to_gregorian()
                    
                    # Convert to datetime with timezone
                    article_datetime = datetime.combine(gregorian_date, datetime.min.time())
                    article_datetime = article_datetime.replace(tzinfo=timezone.utc)
                    
                    # Check if article is within max_age_days
                    time_diff = current_time - article_datetime
                    if time_diff <= timedelta(days=self.max_age_days):
                        formatted_date = article_datetime.strftime('%Y-%m-%d')
                        result.append(ArticleLinkModel(
                            link=link,
                            date=formatted_date
                        ))
                except Exception as e:
                    logger.error(f"Error parsing date {date_text}: {e}")

            except Exception as e:
                logger.error(f"Error processing article: {e}")

        logger.info(f"Found {len(result)} articles within the last {self.max_age_days} days")

        # Sort articles from newest to oldest
        result.sort(key=lambda x: x.date, reverse=True)
        return result
        
    def get_article_content(self, url: str, date: str) -> Optional[ArticleContentModel]:
        """
        Get article content from a Defier article page.
        """
        soup = self.get_soup(url)
        
        if not soup:
            logger.error(f"Failed to fetch and parse URL: {url}")
            return None
        
        try:
            # Extract the data content, keeping the HTML tags
            article_content = soup.select_one('article')
            if not article_content:
                logger.error(f"Could not find article content for: {url}")
                return None
            
            data_html = article_content.decode_contents()

            # Extract the creator - look for the author byline
            creator = soup.select_one('article .author') or soup.select_one('article .creator')
            creator_name = creator.get_text(strip=True) if creator else "Defier"

            # Extract the title
            title = soup.select_one('h1')
            title_text = title.get_text(strip=True) if title else "Unknown Title"
            
            # Extract thumbnail image
            thumbnail_image = self.extract_thumbnail_image(soup)
            
            # Create and return the model
            return ArticleContentModel(
                link=url,
                date=date,
                data=data_html,
                creator=creator_name,
                title=title_text,
                thumbnail_image=thumbnail_image 
            )
        
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            return None
            
    def process_article_content(self, article: ArticleContentModel) -> Optional[ArticleFullModel]:
        """
        Process Defier article content to extract structured data.
        
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
            
            # Upload thumbnail image
            uploaded_thumbnail_url = None
            if article.thumbnail_image:
                logger.info(f"Uploading thumbnail: {article.thumbnail_image}")
                uploaded_thumbnail_url = self.api_client.upload_image(article.thumbnail_image)
                logger.info(f"Thumbnail uploaded to: {uploaded_thumbnail_url}")
            else:
                logger.warning(f"No thumbnail found to upload for {article.link}")
            
            # Extract and process images
            html_with_placeholders, images = self.extract_and_replace_images(html_content)
            
            # Upload additional images and update their URLs
            uploaded_images = []
            for img_data in images:
                original_url = img_data.get('url')
                if original_url:
                    logger.info(f"Uploading image: {original_url}")
                    new_url = self.api_client.upload_image(original_url)
                    logger.info(f"Image uploaded to: {new_url}")
                    img_data['url'] = new_url  # Update the URL in the dictionary
                else:
                    logger.warning(f"Image data missing URL: {img_data}")
                uploaded_images.append(img_data)
            
            # Extract content
            content = self.extract_content(html_with_placeholders)
            
            # Use the title from the article model
            title = article.title
            
            # Extract tags
            tags = self.extract_tags(html_content)
            
            # Create ImageModel objects for each uploaded image
            image_models = [
                ImageModel(
                    id=img['id'],
                    url=img['url'],  # Use the uploaded URL
                    caption=img['caption'],
                    type=img['type']
                ) for img in uploaded_images
            ]
            
            # Create article data using uploaded URLs
            article_data = ArticleFullModel(
                title=title,
                source="Defier",
                sourceUrl=article.link,
                publishDate=article.date,
                creator=article.creator,
                thumbnailImage=uploaded_thumbnail_url, # Use the uploaded thumbnail URL
                content=content,
                tags=tags,
                imagesUrl=image_models, # Use models with uploaded URLs
                sourceDate=article.date
            )
            
            return article_data
                
        except Exception as e:
            logger.error(f"Error processing article content for {article.link}: {e}")
            return None
            
    def extract_thumbnail_image(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract the thumbnail image from the article HTML.
        """
        try:
            # Look for the main article image
            featured_img = soup.select_one('article img') or soup.select_one('header img')
            if featured_img and 'src' in featured_img.attrs:
                return featured_img['src']
                
            # Try other common selectors
            meta_image = soup.select_one('meta[property="og:image"]')
            if meta_image and 'content' in meta_image.attrs:
                return meta_image['content']
        except Exception as e:
            logger.error(f"Error extracting thumbnail image: {e}")
            
        return None
        
    def extract_and_replace_images(self, html: str) -> Tuple[str, List[Dict]]:
        """
        Extract images from HTML content and replace them with placeholders.
        
        Args:
            html: HTML content to process
            
        Returns:
            Tuple of (HTML with image placeholders, list of extracted image data)
        """
        soup = BeautifulSoup(html, 'html.parser')
        images = []
        img_id = 0
        
        # Find all img tags
        img_tags = soup.find_all('img')
        for img in img_tags:
            try:
                if not img.has_attr('src'):
                    continue
                    
                img_id += 1
                img_url = img['src']
                
                # Check if the image URL is valid
                if not img_url or img_url.startswith('data:'):
                    continue
                    
                # Create a placeholder to be replaced later
                placeholder = f"__IMAGE_PLACEHOLDER_{img_id}__"
                
                # Extract image caption from surrounding elements
                caption = ""
                figcaption = img.find_parent('figure').find('figcaption') if img.find_parent('figure') else None
                if figcaption:
                    caption = figcaption.get_text(strip=True)
                
                # Create image data
                image_data = {
                    'id': img_id,
                    'url': img_url,
                    'caption': caption,
                    'type': 'image'
                }
                
                images.append(image_data)
                
                # Replace the img with placeholder
                img.replace_with(BeautifulSoup(placeholder, 'html.parser'))
                
            except Exception as e:
                logger.error(f"Error extracting image: {e}")
        
        return str(soup), images
        
    def extract_content(self, html: str) -> Dict:
        """
        Extract and structure content from HTML.
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find all paragraphs in main content area
        paragraphs = []
        content_sections = []
        
        # Get all paragraph-like elements
        p_elements = soup.find_all(['p', 'h2', 'h3', 'h4', 'blockquote', 'ul', 'ol'])
        
        for elem in p_elements:
            # Skip elements in excluded containers
            if self.is_in_excluded_container(str(soup), soup.decode_contents().find(str(elem))):
                continue
                
            elem_html = str(elem)
            
            # Handle image placeholders in paragraph
            if '__IMAGE_PLACEHOLDER_' in elem_html:
                content_sections.append({
                    "type": "paragraph",
                    "content": paragraphs
                })
                paragraphs = []
                
                # Add image section
                image_id_match = re.search(r'__IMAGE_PLACEHOLDER_(\d+)__', elem_html)
                if image_id_match:
                    image_id = int(image_id_match.group(1))
                    content_sections.append({
                        "type": "image",
                        "id": image_id
                    })
            else:
                # Process paragraph
                text = elem.get_text(strip=True)
                if text:
                    paragraphs.append(text)
        
        # Add remaining paragraphs
        if paragraphs:
            content_sections.append({
                "type": "paragraph",
                "content": paragraphs
            })
        
        return {
            "sections": content_sections
        }
        
    def extract_tags(self, html: str) -> List[str]:
        """
        Extract tags from article HTML.
        """
        soup = BeautifulSoup(html, 'html.parser')
        tags = []
        
        # Look for tag elements - these are typically in a tags section or category links
        tag_elements = soup.select('.tags a') or soup.select('.categories a') or soup.select('.topics a')
        
        for tag_elem in tag_elements:
            tag_text = tag_elem.get_text(strip=True)
            if tag_text and tag_text not in tags:
                tags.append(tag_text)
                
        # If no tags found, extract from meta keywords
        if not tags:
            meta_keywords = soup.select_one('meta[name="keywords"]')
            if meta_keywords and meta_keywords.has_attr('content'):
                keywords = meta_keywords['content'].split(',')
                tags = [k.strip() for k in keywords if k.strip()]
                
        return tags
        
    def is_in_excluded_container(self, html: str, position: int) -> bool:
        """Check if the given position is within an excluded container."""
        # Define patterns for elements to exclude (comments, headers, footers, sidebars, etc.)
        excluded_patterns = [
            r'<footer.*?>.*?</footer>',
            r'<aside.*?>.*?</aside>',
            r'<nav.*?>.*?</nav>',
            r'<div[^>]*class="[^"]*comment[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*class="[^"]*sidebar[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*class="[^"]*related[^"]*"[^>]*>.*?</div>'
        ]
        
        for pattern in excluded_patterns:
            for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
                if match.start() <= position <= match.end():
                    return True
        
        return False
        
    def _convert_persian_numbers(self, persian_str: str) -> str:
        """
        Convert Persian/Arabic numerals to English numerals.
        """
        mapping = {
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
            '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
        }
        
        for persian_digit, english_digit in mapping.items():
            persian_str = persian_str.replace(persian_digit, english_digit)
            
        return persian_str 