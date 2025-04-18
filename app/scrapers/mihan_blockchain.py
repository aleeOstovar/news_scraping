import logging
import re
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup,NavigableString
from persiantools.jdatetime import JalaliDateTime

from app.core.config import settings
from app.models.article import ArticleLinkModel, ArticleContentModel, ArticleFullModel, ImageModel
from app.scrapers.base_scraper import BaseScraper
from app.services.api_client import APIClient

logger = logging.getLogger(__name__)

class MihanBlockchainScraper(BaseScraper):
    """
    Scraper for MihanBlockchain news website.
    """
    
    def __init__(self, api_client: APIClient, max_age_days: int = 3):
        """
        Initialize the MihanBlockchain scraper.
        
        Args:
            api_client: An instance of the APIClient for uploading images.
            max_age_days: Maximum age of articles to scrape in days
        """
        super().__init__("MihanBlockchain", max_age_days)
        self.api_client = api_client
        
    def get_article_links(self, url: str) -> List[ArticleLinkModel]:
        """
        Get article links from the MihanBlockchain news page.
        """
        result = []
        soup = self.get_soup(url)
        
        if not soup:
            logger.error(f"Failed to fetch and parse URL: {url}")
            return result
            

        current_time = datetime.now(timezone.utc)
        

        articles = soup.select('div.jnews_category_content_wrapper > div.jeg_postblock_4.jeg_postblock > div.jeg_posts.jeg_block_container > div.jeg_posts > article.jeg_post')
        
        logger.info(f"Found {len(articles)} total articles on the page, will collect all within the past {self.max_age_days} days")
        
        for article in articles:
            try:

                link_element = article.select_one('h3.jeg_post_title > a')
                if not link_element or not link_element.has_attr('href'):
                    continue
                    
                link = link_element['href'].strip()
                

                date_element = article.select_one('div.jeg_meta_date > a')
                if not date_element:
                    continue
                    
                date_str = date_element.get_text(strip=True)
                
                try:

                    date_parts = date_str.split()
                    if len(date_parts) >= 3:
                        day = int(date_parts[0])
                        month_name = date_parts[1]
                        year = int(date_parts[2])
                        
                        # Convert Persian month name to number
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
        Get article content from a MihanBlockchain article page.
        """
        soup = self.get_soup(url)
        
    
        if not soup:
            logger.error(f"Failed to fetch and parse URL: {url}")
            return None
        
        try:

            data = soup.select_one('div.jeg_inner_content')
            if not data:
                logger.error(f"Could not find content div for article: {url}")
                return None
            
            data_html = data.decode_contents()


            creator = soup.select_one('div.jeg_meta_container > div.jeg_post_meta.jeg_post_meta_1 > div.meta_left > div.jeg_meta_author > a')
            creator_name = creator.get_text(strip=True) if creator else "N/A"


            title = soup.select_one('div.entry-header > h1.jeg_post_title')
            title_text = title.get_text(strip=True) if title else "N/A"
            

            thumbnail_image = self.extract_thumbnail_image(data_html)
            logger.info(f"Extracted thumbnail in get_article_content: {thumbnail_image}")
            data_html = soup.select_one('div.entry-content').decode_contents()

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
        Process Mihan Blockchain article content to extract structured data.
        
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
            

            html_with_placeholders, images = self.extract_and_replace_images(html_content)
            

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
            

            content = self.extract_content(html_with_placeholders)
            
            title = article.title
            
           
            tags = self.extract_tags(html_content)
            
            
            image_models = [
                ImageModel(
                    id=img['id'],
                    url=img['url'],  
                    caption=img['caption'],
                    type=img['type']
                ) for img in uploaded_images
            ]
            
           
            article_data = ArticleFullModel(
                title=title,
                source="Mihan Blockchain",
                sourceUrl=article.link,
                publishDate=article.date,
                creator=article.creator,
                thumbnailImage=uploaded_thumbnail_url, 
                content=content,
                tags=tags,
                imagesUrl=image_models, 
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

            featured_img = soup.select_one('div.jeg_featured > a > div.thumbnail-container')
            if featured_img:
                img_tag = featured_img.select_one('img')
                if img_tag and 'data-lazy-src' in img_tag.attrs:
                    return img_tag['data-lazy-src']
            
                
        except Exception as e:
            logger.error(f"Error extracting thumbnail image: {e}")
            
        return None
        
    def extract_and_replace_images(self,html: str) -> tuple[str, list[dict]]:
        """
        Extract images from the article HTML and replace them with placeholders.
        
        Args:
            html: HTML content of the article
            
        Returns:
            Tuple containing the processed HTML with placeholders and list of image data.
        """
        processed_html = html
        images_url = []
        processed_urls = set()
        
        figure_regex = (
            r'<div class="wp-block-image">.*?'              
            r'<figure[^>]*>'                              
            r'.*?'                                         
            r'<a[^>]*>'                                 
            r'.*?'                                        
            r'<img[^>]*data-lazy-src="([^"]+)"[^>]*>'       
            r'.*?</a>'                                    
            r'.*?'                                         
            r'(?:<figcaption[^>]*>(.*?)</figcaption>)?'     
            r'.*?</figure>'                                 
            r'.*?</div>'                                  
            )          
        image_counter = 0
        
        for match in re.finditer(figure_regex, html, re.IGNORECASE | re.DOTALL):
            full_match = match.group(0)
            match_position = match.start()
            image_url = match.group(1)
            

            if self.is_in_excluded_container(html, match_position) or image_url in processed_urls:
                continue
            

            caption_html = match.group(2)
            caption = re.sub(r'<[^>]+>', '', caption_html).strip() if caption_html else None
            
            image_id = f"img{image_counter}"
            placeholder = f"<figure>**IMAGE_PLACEHOLDER_{image_id}** </figure>"
            
            images_url.append({
                'id': image_id,
                'url': image_url,
                'caption': caption,
                'type': 'figure'
            })
            

            processed_html = processed_html.replace(full_match, placeholder)
            processed_urls.add(image_url)
            image_counter += 1
        
        return processed_html, images_url

    def extract_content(self,html: str) -> dict:
        """
        Extract content elements from the article HTML and return a dict with dynamic keys.
        Headings stored as hN0, hN1... Paragraphs as p0, p1... Blockquotes as blockquote0...
        Text extraction uses spaces as separators.
        Handles blockquotes containing only a single <p> tag.
        Removes EZ Table of Contents elements before processing.
        Figures with image placeholders are extracted. Unwanted divs/tags removed.
        """
        html = self.fix_html_paragraphs(html)
        soup = BeautifulSoup(html, 'html.parser')
        content_elements = {}

        content_container = soup.select_one('article.main-article')
        if not content_container:
            content_container = soup.select_one('div.article-content')
        if not content_container:
            content_container = soup.body if soup.body else soup

        # --- Remove specific unwanted sections FIRST ---

        toc_container = content_container.select_one("#ez-toc-container")
        if toc_container:
            toc_container.decompose()

        toc_title = content_container.select_one("p.ez-toc-title")
        if toc_title:
            toc_title.decompose()


        toc_list = content_container.select_one("nav > ul.ez-toc-list")
        if toc_list:
            toc_nav = toc_list.find_parent('nav')
            if toc_nav:

                if toc_nav in content_container.find_all(recursive=False) or toc_nav.find_parent(content_container.name, id=content_container.get('id'), class_=content_container.get('class')):
                    toc_nav.decompose()
            else:
                
                if toc_list.parent:
                    toc_list.decompose()

        # --- Remove other general unwanted tags ---
        general_unwanted_selectors = [
            "div.jeg_post_source", "div.jeg_post_tags",
            "script", "style", "noscript",
            "header", "footer", "aside" 
        ]
        for selector in general_unwanted_selectors:

            for element in content_container.select(selector):

                if element.parent:
                    element.decompose()

        # --- Initialize counters and start processing content ---
        counters = {
            'p': 0, 'img': 0, 'h1': 0, 'h2': 0, 'h3': 0, 'h4': 0, 'h5': 0, 'h6': 0,
            'blockquote': 0, 'figure': 0, 'li': 0,
        }

        relevant_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'figure', 'blockquote', 'li']
        processed_element_ids = set()
        

        for element in content_container.find_all(relevant_tags, recursive=True):
            element_id = id(element)
            if element_id in processed_element_ids:
                continue

            tag_name = element.name
            key = None
            target_element_for_text = element


            if tag_name == 'figure':
                if any(parent.name == 'blockquote' for parent in element.parents):

                    processed_element_ids.add(element_id)
                    continue

                img_placeholder = element.find(string=re.compile(r'\*\*IMAGE_PLACEHOLDER_img\d+\*\*'))
                if img_placeholder:
                    placeholder_text = img_placeholder.strip()
                    figure_text_check = element.get_text(separator=" ", strip=True)
                    if figure_text_check == placeholder_text:
                        key = f"img{counters['img']}"
                        content_elements[key] = placeholder_text
                        counters['img'] += 1
                        processed_element_ids.add(element_id)
                        continue

            elif tag_name == 'blockquote':
                key = f"blockquote{counters['blockquote']}"
                counters['blockquote'] += 1
                
                inner_html = element.decode_contents()
                cleaned_html = inner_html.strip()
                
                if not cleaned_html:
                    processed_element_ids.add(element_id)
                    counters['blockquote'] -= 1
                    continue
                
                content_elements[key] = cleaned_html
                
                for child in element.find_all(recursive=True):
                    processed_element_ids.add(id(child))
                    
                processed_element_ids.add(element_id)
                continue  

            elif tag_name.startswith('h'):
                key = f"{tag_name}{counters[tag_name]}"
                counters[tag_name] += 1
            elif tag_name == 'p':
                if any(parent.name == 'blockquote' for parent in element.parents):
                    processed_element_ids.add(element_id)
                    continue
                    
                key = f"p{counters['p']}"
                counters['p'] += 1
            elif tag_name == 'li':
                key = f"li{counters['li']}"
                counters['li'] += 1

            if key is None:
                processed_element_ids.add(element_id)
                continue

            text = target_element_for_text.get_text(separator=" ", strip=True)
            text = re.sub(r'\s+', ' ', text).strip()

            if not text:
                processed_element_ids.add(element_id)
                if key.startswith('p'): counters['p'] -= 1
                elif key.startswith('h'): counters[tag_name] -= 1
                elif key.startswith('li'): counters['li'] -=1
                continue

            text_before_placeholder_removal = text
            text = re.sub(r'\s*\*\*IMAGE_PLACEHOLDER_img\d+\*\*\s*', ' ', text).strip()

            if not text and text_before_placeholder_removal:
                processed_element_ids.add(element_id)
                if key.startswith('p'): counters['p'] -= 1
                elif key.startswith('h'): counters[tag_name] -= 1
                elif key.startswith('li'): counters['li'] -=1
                continue

            content_elements[key] = text
            processed_element_ids.add(element_id)

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
            tag_container = soup.select_one('div.jeg_post_tags')
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
        Scrape articles from MihanBlockchain website.
        
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