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

class ArzDigitalScraper(BaseScraper):
    """
    Scraper for ArzDigital news website.
    """
    
    def __init__(self, api_client=APIClient, max_age_days: int = 3):
        """
        Initialize the ArzDigital scraper.
        
        Args:
            api_client: API client for sending data
            max_age_days: Maximum age of articles to scrape in days
        """
        super().__init__("ArzDigital", max_age_days)
        if api_client:
            self.api_client = api_client
        
    def get_article_links(self, url: str) -> List[ArticleLinkModel]:
        """
        Get article links from the ArzDigital news page.
        """
        result = []
        soup = self.get_soup(url)

        if not soup:
            logger.error(f"Failed to fetch and parse URL: {url}")
            return result

        current_time = datetime.now(timezone.utc)

        articles = soup.select('div.arz-breaking-news__list > div.arz-breaking-news__item')

        logger.info(f"Found {len(articles)} total articles on the page, will collect all within the past {self.max_age_days} days")

        for article in articles:
            try:
                # Extract the link
                link_element = article.select_one('a.arz-breaking-news__item-link')
                if not link_element or not link_element.has_attr('href'):
                    continue

                link = link_element['href'].strip() # Use strip() to remove leading/trailing whitespace

                # --- ADDED CHECK: Skip ad links ---
                AD_LINK_PREFIX = "https://adcmp " # Define the prefix to check against
                if link.startswith(AD_LINK_PREFIX):
                    logger.debug(f"Skipping ad link: {link}")
                    continue # Go to the next article

                # Extract the <time> tag and its datetime attribute
                time_element = article.select_one(
                    'a.arz-breaking-news__item-link > div.arz-tw-flex > div.arz-breaking-news__info > '
                    'div.arz-breaking-news-post__info-publish-date.arz-breaking-news__publish-time.'
                    'arz-tw-truncate.arz-tw-w-20 > time'
                )
                if not time_element or not time_element.has_attr('datetime'):
                    continue

                date_str = time_element['datetime']

                try:
                    # Parse the datetime (assumed format: yyyy-mm-dd)
                    article_datetime = datetime.strptime(date_str, "%Y-%m-%d")
                    article_datetime = article_datetime.replace(tzinfo=timezone.utc)

                    # Check article age
                    max_days = min(self.max_age_days, 3)
                    time_diff = current_time - article_datetime

                    if time_diff <= timedelta(days=max_days):
                        formatted_date = article_datetime.strftime('%Y-%m-%d')
                        result.append(ArticleLinkModel(
                            link=link,
                            date=formatted_date
                        ))

                except Exception as e:
                    logger.error(f"Error parsing datetime {date_str}: {e}")

            except Exception as e:
                logger.error(f"Error processing article: {e}")

        logger.info(f"Found {len(result)} articles within the last {min(self.max_age_days, 3)} days")

        # Sort articles from newest to oldest
        result.sort(key=lambda x: x.date, reverse=True)
        return result
        
    def get_article_content(self, url: str, date: str) -> Optional[ArticleContentModel]:
        """
        Get article content from a ArzDigital article page.
        """
        soup = self.get_soup(url)
        
    
        if not soup:
            logger.error(f"Failed to fetch and parse URL: {url}")
            return None
        
        try:
            # Extract the data content, keeping the HTML tags
            data = soup.select_one('section.arz-container.arz-breaking-news-post > article')
            if not data:
                logger.error(f"Could not find content div for article: {url}")
                return None
            
            data_html = data.decode_contents()

            # Extract the creator
            creator = soup.select_one('section > a.arz-tw-text-sm')
            creator_name = creator.get_text(strip=True) if creator else "N/A"

            # Extract the title
            title = soup.select_one('header > h1.arz-breaking-news-post__title')
            title_text = title.get_text(strip=True) if title else "N/A"
            
            # Extract thumbnail image here
            thumbnail_image = self.extract_thumbnail_image(data_html)
            logger.info(f"Extracted thumbnail in get_article_content: {thumbnail_image}")
            data = soup.select_one('section.arz-container.arz-breaking-news-post')
            data_html = data.decode_contents()
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
        Process ArzDigital article content to extract structured data.
        
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
                source="Arzdigital",
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
        
        # Look for the thumbnail image
        try:
            # First try to find the featured image
            featured_img = soup.select_one('header > figure.arz-breaking-news-post__image-container ')
            if featured_img:
                img_tag = featured_img.select_one('img')
                if img_tag and 'src' in img_tag.attrs:
                    return img_tag['src']   
        except Exception as e:
            logger.error(f"Error extracting thumbnail image: {e}")
            
        return None
        
    def extract_and_replace_images(self,html: str) -> tuple[str, list[dict]]:
        """
        right now arzdigital has no images in the articles
        """
        processed_html = html
        images_url = []
        return processed_html, images_url

    def extract_content(self, html: str) -> dict:
        """
        right now arzdigital has only p tags in the articles
        Returns a dictionary with keys like p0, p1, ..., each containing the paragraph text.
        Cleans extra whitespace and ignores empty paragraphs.
        """
        html = self.fix_html_paragraphs(html)
        soup = BeautifulSoup(html, 'html.parser')
        content_elements = {}

        content_container = soup.select_one('article > section > div.arz-post__content')
        if not content_container:
            content_container = soup.body if soup.body else soup

        p_counter = 0

        for p in content_container.find_all('p', recursive=True):
            text = p.get_text(separator=" ", strip=True)
            text = re.sub(r'\s+', ' ', text).strip()

            if not text:
                continue

            content_elements[f"p{p_counter}"] = text
            p_counter += 1

        return content_elements
            
    def extract_tags(self, html: str) -> List[str]:
        """
        Extract tags from the article HTML.
        This version looks inside the path container and skips the first 2 and last tag.
        Args:
            html: HTML content of the article
        Returns:
            List of tags
        """
        soup = BeautifulSoup(html, 'html.parser')
        tags = []

        try:
            # Find all tag elements along the given path
            tag_elements = soup.select(
                'div.arz-breaking-news-post__path > div.arz-path > ul.arz-path-list > li.arz-path__item > a.arz-path-link > span.arz-path-text'
            )

            # Skip first 2 and last
            relevant_tags = tag_elements[1:]

            for tag in relevant_tags:
                tag_text = tag.get_text(strip=True)
                if tag_text and tag_text not in tags:
                    tags.append(tag_text)

            # Limit to a maximum of 10 tags
            return tags[:10]

        except Exception as e:
            logger.error(f"Error extracting tags: {e}")
            return []
    

    def is_in_excluded_container(self, html: str, position: int) -> bool:
        """
        right now arzdigital has no excluded containers
        """
        pass
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
        """
        # This pattern matches any HTML tag for p, h1-h6, figure, or blockquote.
        # It captures whether the tag is closing (group 2) and its tag type (group 3).
        pattern = re.compile(
            r'(<\s*(/)?\s*(p|h[1-6]|figure|blockquote)\b[^>]*>)', 
            re.IGNORECASE
        )
        
        result = []
        last_index = 0
        p_opened = False

        for match in pattern.finditer(html_content):
            full_tag = match.group(1)      # The full matched tag
            is_closing = bool(match.group(2))  # True if it's a closing tag (e.g. </p>)
            tag_type = match.group(3).lower()  # The tag type, e.g., 'p', 'h1', etc.
            start, end = match.span(1)
            
            # Append the text between the previous match and the current tag.
            result.append(html_content[last_index:start])
            
            # If we encounter an opening tag (not a closing tag) that is one of our triggers,
            # and if there's an open <p> that hasn't been closed yet, insert a closing </p>.
            if not is_closing and tag_type in ('p', 'figure', 'blockquote') or (not is_closing and tag_type.startswith('h')):
                if p_opened:
                    result.append('</p>')
                    p_opened = False
            
            # Append the current tag.
            result.append(full_tag)
            
            # Update the p_opened flag:
            # - For an opening <p> tag, mark that a paragraph is open.
            # - For a closing </p> tag, mark that the paragraph is closed.
            if tag_type == 'p':
                if is_closing:
                    p_opened = False
                else:
                    p_opened = True

            last_index = end

        # Append any remaining text after the last tag.
        result.append(html_content[last_index:])
        
        # If there's an unclosed <p> at the end of the content, close it.
        if p_opened:
            result.append('</p>')
        
        return ''.join(result)

    def scrape_articles(self, base_url: str) -> List[ArticleFullModel]:
        """
        Scrape articles from ArzDigital website.
        
        Args:
            base_url: Base URL of the website
            
        Returns:
            List of processed articles
        """
        articles = []
        
        # Get article links
        article_links = self.get_article_links(base_url)
        logger.info(f"Found {len(article_links)} article links")
        
        # Process each article
        for i, article_link in enumerate(article_links):
            logger.info(f"Processing article {i+1}/{len(article_links)}: {article_link.link}")
            
            # Get article content
            content = self.get_article_content(article_link.link, article_link.date)
            if not content:
                logger.warning(f"Failed to get content for article: {article_link.link}")
                continue
                
            # Process article content
            processed = self.process_article_content(content)
            if not processed:
                logger.warning(f"Failed to process content for article: {article_link.link}")
                continue
                
            # Add to list of articles
            articles.append(processed)
            
        return articles 