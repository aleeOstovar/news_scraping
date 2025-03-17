import logging
import re
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from persiantools.jdatetime import JalaliDateTime

from app.config import PERSIAN_MONTHS
from app.models.article import ArticleLinkModel, ArticleContentModel, ArticleFullModel, ImageModel
from app.scrapers.base_scraper import BaseScraper
from app.services.api_client import APIClient

logger = logging.getLogger(__name__)

class MihanBlockchainScraper(BaseScraper):
    """
    Scraper for MihanBlockchain news website.
    """
    
    def __init__(self, max_age_days: int = 8):
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
        current_time = datetime.now(datetime.timezone.utc)
        
        # Select the articles using CSS selectors
        articles = soup.select('div.jnews_category_content_wrapper > div.jeg_postblock_4.jeg_postblock > div.jeg_posts.jeg_block_container > div.jeg_posts > article.jeg_post')
        
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
                    time_diff = current_time - utc_datetime.replace(tzinfo=datetime.timezone.utc)
        
                    # Only add if within max age
                    if time_diff <= timedelta(days=self.max_age_days):
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
                
        logger.info(f"Found {len(result)} articles within the last {self.max_age_days} days")
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
                
            # Extract thumbnail image
            thumbnail_image = self.extract_thumbnail_image(html_content)
            
            # Extract and process images
            processed_html, images_url = self.extract_and_replace_images(html_content)
            
            # Extract content
            content_list = self.extract_content(processed_html)
            
            # Extract tags
            tags = self.extract_tags(html_content)
            
            # Upload thumbnail image if found
            if thumbnail_image:
                thumbnail_image = self.api_client.upload_image(thumbnail_image)
            elif images_url:
                # Use the first image as thumbnail if no dedicated thumbnail is found
                thumbnail_image = images_url[0].url
                
            # Upload content images
            for image in images_url:
                original_url = image.url
                new_url = self.api_client.upload_image(original_url)
                image.url = new_url
                
            # Create and return the full article model
            return ArticleFullModel(
                title=article.title,
                sourceUrl=article.link,
                sourceDate=article.date,
                creator=article.creator,
                thumbnailImage=thumbnail_image,
                content=content_list,
                imagesUrl=images_url,
                tags=tags
            )
            
        except Exception as e:
            logger.error(f"Error processing article content for {article.link}: {e}")
            return None
            
    # Helper methods for processing content
    
    def extract_thumbnail_image(self, html: str) -> Optional[str]:
        """Extract the thumbnail image URL from the HTML content."""
        try:
            # Try different patterns to find the thumbnail
            patterns = [
                r'<div[^>]*class="[^"]*jeg_featured[^"]*"[^>]*>.*?<a[^>]*>.*?<div[^>]*class="[^"]*thumbnail-container[^"]*"[^>]*>.*?<img[^>]*data-lazy-src="([^"]+)"',
                r'<div[^>]*class="[^"]*jeg_featured[^"]*"[^>]*>.*?<a[^>]*>.*?<div[^>]*class="[^"]*thumbnail-container[^"]*"[^>]*>.*?<img[^>]*data-src="([^"]+)"',
                r'<div[^>]*class="[^"]*jeg_featured[^"]*"[^>]*>.*?<a[^>]*>.*?<div[^>]*class="[^"]*thumbnail-container[^"]*"[^>]*>.*?<img[^>]*data-lazy-srcset="([^"]+)"',
                r'<div[^>]*class="[^"]*jeg_featured[^"]*"[^>]*>.*?<a[^>]*>.*?<div[^>]*class="[^"]*thumbnail-container[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    url = match.group(1)
                    
                    # If it's a srcset, extract the first URL
                    if ',' in url:
                        url = url.split(',')[0].strip().split(' ')[0]
                        
                    # Skip data URLs
                    if url.startswith('data:'):
                        continue
                        
                    return url
                    
            return None
        except Exception as e:
            logger.error(f"Error extracting thumbnail image: {e}")
            return None
            
    def extract_and_replace_images(self, html: str) -> Tuple[str, List[ImageModel]]:
        """Extract images from the HTML content and replace them with placeholders."""
        processed_html = html
        images_url = []
        processed_urls = set()
        image_counter = 0
        
        # Define patterns for finding images
        patterns = [
            # Figure with src attribute
            (r'<figure[^>]*>[\s\S]*?<a[^>]*>[\s\S]*?<img[^>]*?src="([^"]+)"[\s\S]*?</a>[\s\S]*?(?:<figcaption[^>]*>([\s\S]*?)</figcaption>)?[\s\S]*?</figure>', 'figure'),
            
            # Figure with data-lazy-src attribute
            (r'<figure[^>]*>[\s\S]*?<a[^>]*>[\s\S]*?<img[^>]*?(?:data-lazy-src="([^"]+)")[\s\S]*?</a>[\s\S]*?(?:<figcaption[^>]*>([\s\S]*?)</figcaption>)?[\s\S]*?</figure>', 'figure'),
            
            # Div with figure, using various src attributes
            (r'<div[^>]*class="[^"]*wp-block-image[^"]*"[^>]*>\s*<figure[^>]*>\s*<a[^>]*>\s*<img[^>]*?(?:data-lazy-src="([^"]+)"|data-src="([^"]+)"|src="([^"]+)").*?</a>(?:\s*<figcaption[^>]*>([\s\S]*?)</figcaption>)?[\s\S]*?</figure>', 'figure'),
            
            # Standalone img elements
            (r'<div[^>]*class="[^"]*wp-block-image[^"]*"[^>]*>\s*<img[^>]*?(?:data-lazy-src="([^"]+)"|data-src="([^"]+)"|src="([^"]+)").*?>(?:\s*<figcaption[^>]*>([\s\S]*?)</figcaption>)?', 'image')
        ]
        
        # Define excluded containers (areas to skip)
        excluded_containers = [
            "jeg_share_bottom_container",
            "jeg_ad_jeg_article_jnews_content_bottom_ads",
            "jnews_prev_next_container",
            "jnews_author_box_container",
            "jnews_related_post_container",
            "jeg_postblock_22 jeg_postblock jeg_module_hook jeg_pagination_disable jeg_col_2o3 jnews_module_307974_0_67c8441ee8156",
            "jnews_popup_post_container",
            "jnews_comment_container"
        ]
        
        # Helper function to check if an element is in an excluded container
        def is_in_excluded_container(html: str, element_position: int) -> bool:
            sample_text = html[element_position:element_position + 100]
            for container in excluded_containers:
                pattern = rf'<div[^>]*class="[^"]*{container}[^"]*"[^>]*>[\\s\\S]*?{re.escape(sample_text)}'
                if re.search(pattern, html, re.IGNORECASE):
                    return True
            return False
        
        # Process each pattern
        for pattern, img_type in patterns:
            for match in re.finditer(pattern, html, re.IGNORECASE):
                full_match = match.group(0)
                match_position = match.start()
                
                # Extract the image URL based on pattern
                if img_type == 'figure':
                    # First pattern - only one capture group for URL
                    if pattern.startswith('<figure') and 'data-lazy-src' not in pattern:
                        image_url = match.group(1)
                        caption = match.group(2)
                    # Second pattern - data-lazy-src pattern
                    elif pattern.startswith('<figure') and 'data-lazy-src' in pattern:
                        image_url = match.group(1)
                        caption = match.group(2)
                    # Third pattern - multiple possible src attributes
                    else:
                        image_url = match.group(1) or match.group(2) or match.group(3)
                        caption = match.group(4)
                else:  # img_type == 'image'
                    image_url = match.group(1) or match.group(2) or match.group(3)
                    caption = match.group(4) if len(match.groups()) >= 4 else None
                
                # Skip if URL is empty or element is in excluded container
                if not image_url or is_in_excluded_container(html, match_position) or image_url in processed_urls:
                    continue
                
                # Skip data URLs
                if image_url.startswith('data:'):
                    # Try to find data-lazy-srcset
                    srcset_match = re.search(r'data-lazy-srcset="([^"]+)"', full_match)
                    if srcset_match:
                        srcset = srcset_match.group(1)
                        image_url = srcset.split(',')[0].strip().split(' ')[0]
                    else:
                        continue
                
                # Clean up caption if present
                if caption:
                    caption = re.sub(r'<[^>]+>', '', caption).strip()
                
                # Create a unique ID and placeholder
                image_id = f'image{image_counter}'
                placeholder = f'**image_{image_id}**'
                
                # Add image info to the list
                images_url.append(ImageModel(
                    id=image_id,
                    url=image_url,
                    caption=caption,
                    type=img_type
                ))
                
                # Replace the original HTML with the placeholder
                processed_html = processed_html.replace(full_match, placeholder)
                processed_urls.add(image_url)
                image_counter += 1
        
        # Remove unwanted content
        patterns_to_remove = [
            r'<div[^>]*class="[^"]*jeg_post_source[^"]*"[^>]*>[\s\S]*?</div>',
            r'<div[^>]*class="[^"]*jeg_post_tags[^"]*"[^>]*>[\s\S]*?</div>'
        ]
        
        for pattern in patterns_to_remove:
            processed_html = re.sub(pattern, '', processed_html)
        
        # Replace content of ez-toc-title with empty text but keep structure
        ez_toc_pattern = r'(<div[^>]*class="[^"]*ez-toc-title-container[^"]*"[^>]*>[\s\S]*?<p[^>]*class="[^"]*ez-toc-title[^"]*"[^>]*>)([\s\S]*?)(</p>[\s\S]*?</div>)'
        processed_html = re.sub(ez_toc_pattern, r'\1\3', processed_html)
        
        return processed_html, images_url
    
    def extract_content(self, html: str) -> List[str]:
        """Extract structured content from the processed HTML."""
        content_array = []
        
        try:
            # Find the main content div
            content_div_pattern = r'<div[^>]*class="[^"]*content-inner[^"]*"[^>]*>([\s\S]*?)<div[^>]*class="[^"]*jeg_share_bottom_container'
            content_div_match = re.search(content_div_pattern, html, re.IGNORECASE)
            
            if not content_div_match:
                # Try a more relaxed pattern
                content_div_pattern = r'<div[^>]*class="[^"]*content-inner[^"]*"[^>]*>([\s\S]*)'
                content_div_match = re.search(content_div_pattern, html, re.IGNORECASE)
                
                if not content_div_match:
                    logger.warning("Could not find content div")
                    return []
            
            content_html = content_div_match.group(1)
            
            # Create a pattern that matches paragraphs, headings, blockquotes, and placeholders
            combined_pattern = r'(<p[^>]*>[\s\S]*?</p>|<blockquote[^>]*>[\s\S]*?</blockquote>|<h[1-6][^>]*>[\s\S]*?</h[1-6]>|\*\*image_image\d+\*\*)'
            
            # Find all matches
            for match in re.finditer(combined_pattern, content_html, re.IGNORECASE):
                content = match.group(1).strip()
                
                # If it's a placeholder, add it directly
                if content.startswith('**image_'):
                    content_array.append(content)
                else:
                    # For HTML content, strip tags and add if non-empty
                    text_content = re.sub(r'<[^>]+>', '', content).strip()
                    if text_content:
                        content_array.append(text_content)
            
            return content_array
        except Exception as e:
            logger.error(f"Error extracting content: {e}")
            return []
    
    def extract_tags(self, html: str) -> List[str]:
        """Extract tags from the HTML content."""
        tags = []
        
        try:
            # Try different patterns to find tags
            patterns = [
                r'<div[^>]*class="[^"]*inner-content[^"]*"[^>]*>.*?<div[^>]*class="[^"]*jeg_post_tags[^"]*"[^>]*>([\s\S]*?)</div>',
                r'<div[^>]*class="[^"]*jeg_post_tags[^"]*"[^>]*>([\s\S]*?)</div>'
            ]
            
            tag_section = None
            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    tag_section = match.group(1)
                    break
            
            if tag_section:
                # Extract individual tags
                for tag_match in re.finditer(r'<a[^>]*>([\s\S]*?)</a>', tag_section, re.IGNORECASE):
                    tag_text = tag_match.group(1).strip()
                    # Remove HTML tags and skip empty/label tags
                    tag_text = re.sub(r'<[^>]+>', '', tag_text).strip()
                    if tag_text and not tag_text.lower() == 'تگ:':
                        tags.append(tag_text)
            
            return tags
        except Exception as e:
            logger.error(f"Error extracting tags: {e}")
            return [] 