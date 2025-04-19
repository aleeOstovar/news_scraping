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
            api_client: An instance of the APIClient for uploading images.
            max_age_days: Maximum age of articles to scrape in days
        """
        super().__init__("Defier", max_age_days)
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
        

        articles = soup.select('main.site-main > div.harika-flex-row > div.main-col > div.page-content > article.post')
        
        logger.info(f"Found {len(articles)} total articles on the page, will collect all within the past {self.max_age_days} days")
        
        for article in articles:
            try:

                link_element = article.select_one('div.content > h2.entry-title> a')
                if not link_element or not link_element.has_attr('href'):
                    continue
                    
                link = link_element['href'].strip()
                

                date_element = article.select_one('div.content > div.archive-meta > div.meta > span.date')
                if not date_element:
                    continue
                    
                date_str = date_element.get_text(strip=True)

                try:
                    date_parts = date_str.split()
                    if len(date_parts) >= 3:
                        day = int(date_parts[0])
                        month_name = date_parts[1]
                        year = int(date_parts[2])

                        month = settings.PERSIAN_MONTHS.get(month_name)
                        if not month:
                            logger.error(f"Unknown Persian month: {month_name}")
                            continue

                        jalali_date = JalaliDateTime(year, month, day)
                        gregorian_date = jalali_date.to_gregorian()

                        article_datetime = datetime(
                            gregorian_date.year,
                            gregorian_date.month,
                            gregorian_date.day,
                            tzinfo=timezone.utc
                        )

                        time_diff = current_time - article_datetime
                        if time_diff <= timedelta(days=self.max_age_days):
                            formatted_date = article_datetime.strftime('%Y-%m-%d')
                            result.append(ArticleLinkModel(
                                link=link,
                                date=formatted_date
                            ))
                            
                except Exception as e:
                    logger.error(f"Error converting date {date_str}: {e}")
                    
            except Exception as e:
                logger.error(f"Error processing article: {e}")
        
        logger.info(f"Found {len(result)} articles within the last {min(self.max_age_days, 3)} days")
        

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

            data = soup.select_one('section.elementor-section > div.elementor-container > div.elementor-column > div.elementor-widget-wrap > section.elementor-section > div.elementor-container > div.elementor-column > div.elementor-widget-wrap   ')
            if not data:
                logger.error(f"Could not find content div for article: {url}")
                return None
            
            data_html = data.decode_contents()


            creator = soup.select_one('div.elementor-element > div.elementor-widget-container > div.harika-metadata-widget > span.author')
            creator_name = creator.get_text(strip=True) if creator else "N/A"


            title = soup.select_one('div.elementor-element > div.elementor-widget-container > h1.elementor-heading-title')
            title_text = title.get_text(strip=True) if title else "N/A"
            

            thumbnail_image = self.extract_thumbnail_image(data_html)
            logger.info(f"Extracted thumbnail in get_article_content: {thumbnail_image}")

            return ArticleContentModel(
                link=url,
                date=date,
                data=data_html,
                creator=creator_name,
                title=title_text,
                thumbnail_image=thumbnail_image # Pass thumbnail here
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
            
            # Create ImageModel objects for each *uploaded* image
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
            
    def extract_thumbnail_image(self, html: str) -> Optional[str]:
        """
        Extract the thumbnail image from the article HTML.
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        
        try:

            featured_img = soup.select_one('div.elementor-element > div.elementor-widget-container > div.harika-featuredimage-widget')
            if featured_img:
                img_tag = featured_img.select_one('img')
                if img_tag and 'src' in img_tag.attrs:
                    return img_tag['src']
            
                
        except Exception as e:
            logger.error(f"Error extracting thumbnail image: {e}")
            
        return None
        
    def extract_and_replace_images(self,html: str) -> tuple[str, list[dict]]:
        """
        right now Defier has no images in the articles
        """
        processed_html = html
        images_url = []
        return processed_html, images_url

    def extract_content(self, html: str) -> dict:
        """
        right now Defier has only p tags in the articles
        Returns a dictionary with keys like p0, p1, ..., each containing the paragraph text.
        Cleans extra whitespace and ignores empty paragraphs.
        """
        html = self.fix_html_paragraphs(html)
        soup = BeautifulSoup(html, 'html.parser')
        content_elements = {}

        content_container = soup.select_one('div.elementor-element.elementor-element-f41c1d8.no-bg.elementor-widget.elementor-widget-theme-post-content')
        if not content_container:
            content_container = soup.body if soup.body else soup

        p_counter = 0
        blockquote_counter = 0
        
        # Get all elements in order, both p and blockquote
        elements = content_container.find_all(['p', 'blockquote'], recursive=True)
        
        for element in elements:
            # Skip paragraphs inside blockquotes
            if element.name == 'p' and element.parent.name == 'blockquote':
                continue
                
            text = element.get_text(separator=" ", strip=True)
            text = re.sub(r'\s+', ' ', text).strip()
            
            if not text:
                continue
                
            if element.name == 'p':
                content_elements[f"p{p_counter}"] = text
                p_counter += 1
            elif element.name == 'blockquote':
                content_elements[f"blockquote{blockquote_counter}"] = text
                blockquote_counter += 1
        
        return content_elements
            
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
            tag_container = soup.select_one('div.elementor-element.elementor-widget-HarikaSACategories > div.elementor-widget-container > div.harika-categories-widget')
            if tag_container:
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
    

    def is_in_excluded_container(self, html: str, position: int) -> bool:
        """
        Check if the given position in HTML is within an excluded container.
        This is a placeholder function - implement according to your exclusion criteria.
        
        Args:
            html: The HTML content
            position: The position to check
            
        Returns:
            True if position is in an excluded container, False otherwise
        """
        excluded_containers = [
        "jeg_share_bottom_container",
        "jeg_ad_jeg_article_jnews_content_bottom_ads",
        "jnews_prev_next_container",
        "jnews_author_box_container",
        "jnews_related_post_container",
        "jeg_postblock_22 jeg_postblock jeg_module_hook jeg_pagination_disable jeg_col_2o3 jnews_module_307974_0_67c3fad848cb2",
        "jnews_popup_post_container",
        "jnews_comment_container",
        ]
        snippet = html[position:position+100]
        
        for container in excluded_containers:
            pattern = r'<div[^>]*class="[^"]*' + re.escape(container) + r'[^"]*"[^>]*>[\s\S]*?' + re.escape(snippet)
            if re.search(pattern, html, re.IGNORECASE):
                return True
        return False
    def fix_html_paragraphs(self,html_content: str) -> str:
        """
        Processes the HTML content to ensure that if a <p> tag is open and one of the following
        tags is encountered as an opening tag:
        - another <p> tag
        - any <h1> to <h6> tag
        - a <figure> tag
        - a <blockquote> tag
        then a closing </p> tag is inserted before the trigger tag.
        
        If a <p> tag is already closed, nothing is added.
        
        Also removes p tags inside blockquotes while preserving their content.
        Additionally removes a tags inside blockquotes while preserving their content and adding a space after.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        for blockquote in soup.find_all('blockquote'):
            for a_tag in blockquote.find_all('a', recursive=True):
                a_text = a_tag.get_text()
                a_tag.replace_with(f"{a_text} ")
            for strong_tag in blockquote.find_all('strong', recursive=True):
                strong_text = strong_tag.get_text()
                strong_tag.replace_with(f"{strong_text} ")
            
            for p_tag in blockquote.find_all('p', recursive=True):
                p_tag.replace_with(*p_tag.contents)
        
        html_content = str(soup)
        
        pattern = re.compile(
            r'(<\s*(/)?\s*(p|h[1-6]|figure|blockquote)\b[^>]*>)', 
            re.IGNORECASE
        )
        
        result = []
        last_index = 0
        p_opened = False

        for match in pattern.finditer(html_content):
            full_tag = match.group(1)   
            is_closing = bool(match.group(2)) 
            tag_type = match.group(3).lower() 
            start, end = match.span(1)
            

            result.append(html_content[last_index:start])
            

            if not is_closing and tag_type in ('p', 'figure', 'blockquote') or (not is_closing and tag_type.startswith('h')):
                if p_opened:
                    result.append('</p>')
                    p_opened = False
            
            result.append(full_tag)
            
            if tag_type == 'p':
                if is_closing:
                    p_opened = False
                else:
                    p_opened = True

            last_index = end

        result.append(html_content[last_index:])
        

        if p_opened:
            result.append('</p>')
        
        return ''.join(result)

    def scrape_articles(self, base_url: str) -> List[ArticleFullModel]:
        """
        Scrape articles from Defier website.
        
        Args:
            base_url: Base URL of the website
            
        Returns:
            List of processed articles
        """
        articles = []
        
        article_links = self.get_article_links(base_url)
        logger.info(f"Found {len(article_links)} article links")
        
        for i, article_link in enumerate(article_links):
            logger.info(f"Processing article {i+1}/{len(article_links)}: {article_link.link}")
            
            content = self.get_article_content(article_link.link, article_link.date)
            if not content:
                logger.warning(f"Failed to get content for article: {article_link.link}")
                continue

            processed = self.process_article_content(content)
            if not processed:
                logger.warning(f"Failed to process content for article: {article_link.link}")
                continue
                
            articles.append(processed)
            
        return articles 