import logging
import time
from typing import Dict, Any, Optional

import requests
from requests.exceptions import RequestException

from app.core.config import settings

logger = logging.getLogger(__name__)

class APIClient:
    """
    Client for interacting with the backend API.
    """
    def __init__(
        self, 
        base_url: str = None, 
        api_key: Optional[str] = None, 
        max_retries: int = 3
    ):
        """
        Initialize the API client
        
        Args:
            base_url: The base URL of the API
            api_key: API key if required
            max_retries: Maximum number of retry attempts for failed requests
        """
        # Use provided values or defaults from settings
        self.base_url = (base_url or settings.API_BASE_URL).rstrip('/')
        
        # Add logging to show the actual base URL being used
        logger.info(f"Using API base URL: {self.base_url}")
        
        self.api_key = api_key or settings.API_KEY
        self.max_retries = max_retries
        self.session = requests.Session()
        
        # Setup headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if self.api_key:
            self.headers['x-api-key'] = self.api_key
            
        logger.info(f"Initialized API client for {self.base_url}")
        
    def build_url(self, endpoint: str) -> str:
        """
        Build a URL for the API endpoint, ensuring proper formatting.
        
        Args:
            endpoint: The API endpoint (e.g., '/news-posts')
            
        Returns:
            The complete URL with base URL and endpoint
        """
        # Ensure the endpoint starts with a slash
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
            
        return f"{self.base_url}{endpoint}"
        
    def post_news_data(self, data: Dict[str, Any]) -> Dict:
        """
        Post news data to the API
        
        Args:
            data: The news data to send
            
        Returns:
            The API response
            
        Raises:
            RequestException: If the request fails after all retries
        """
        url = self.build_url('/news-posts')
        
        # Log data summary for debugging
        data_summary = {
            "title": data.get('title', 'N/A'),
            "sourceUrl": data.get('sourceUrl', 'N/A'),
            "content_length": len(data.get('content', [])) if isinstance(data.get('content', []), list) else 'Not a list',
            "imagesUrl_count": len(data.get('imagesUrl', [])) if isinstance(data.get('imagesUrl', []), list) else 'Not a list',
            "tags_count": len(data.get('tags', [])) if isinstance(data.get('tags', []), list) else 'Not a list',
        }
        logger.info(f"Preparing to send article: {data_summary}")
        
        # Ensure imagesUrl is formatted correctly (as array of objects, not strings)
        images_url = data.get('imagesUrl', [])
        if isinstance(images_url, list) and len(images_url) > 0:
            if isinstance(images_url[0], str):
                # Convert string URLs to proper objects
                logger.info("Converting imagesUrl from string array to object array")
                data['imagesUrl'] = [
                    {
                        "id": f"img{idx}",
                        "url": url,
                        "caption": "",
                        "type": "figure"
                    } for idx, url in enumerate(images_url)
                ]
            elif hasattr(images_url[0], 'dict') and callable(getattr(images_url[0], 'dict', None)):
                # Convert Pydantic models to dictionaries
                logger.info("Converting imagesUrl from Pydantic models to dictionaries")
                data['imagesUrl'] = [img.dict() for img in images_url]
        
        # Log the complete payload - this is very important for debugging
        logger.info(f"Complete article payload: {data}")
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Sending data to {url} (Attempt {attempt + 1}/{self.max_retries})")
                response = self.session.post(
                    url=url,
                    json=data,
                    headers=self.headers
                )
                
                # Log response status
                logger.info(f"Response status code: {response.status_code}")
                
                # If we got an error response but not an exception, log it
                if response.status_code >= 400:
                    try:
                        error_content = response.json()
                        logger.error(f"Error response from API: {error_content}")
                    except Exception:
                        logger.error(f"Error response from API (not JSON): {response.text[:500]}")
                
                response.raise_for_status()
                response_data = response.json()
                logger.info(f"Successfully sent article: {data.get('title', 'Unknown')} to API, received response: {response_data}")
                return response_data
                
            except RequestException as e:
                # Log detailed error info
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                
                # Try to extract more detail from the response if available
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_content = e.response.json()
                        logger.error(f"Error details from API: {error_content}")
                    except Exception:
                        logger.error(f"Error response (not JSON): {e.response.text[:500] if e.response.text else 'Empty response'}")
                
                if attempt == self.max_retries - 1:
                    logger.error(f"All {self.max_retries} attempts to send article failed: {data.get('title', 'Unknown')}")
                    
                    # Log a specific error for articles that fail to post
                    error_msg = f"⚠️ ARTICLE POST FAILED: '{data.get('title', 'Unknown')}' ({data.get('sourceUrl', 'Unknown')}) - All {self.max_retries} attempts failed"
                    logger.error(error_msg)
                    
                    raise
                
                # Exponential backoff before retry
                sleep_seconds = 2 ** attempt
                logger.info(f"Waiting {sleep_seconds} seconds before retry...")
                time.sleep(sleep_seconds)
                
        raise RequestException("Failed to send data after all retry attempts")
    
    def check_article_exists(self, source_url: str) -> bool:
        """
        Check if an article with the given source URL already exists in the database.
        
        Args:
            source_url: The URL of the article to check
            
        Returns:
            True if the article exists, False otherwise
        """
        url = self.build_url('/news-posts/check')
        
        try:
            logger.info(f"Checking if article exists: {source_url}")
            response = self.session.post(
                url=url,
                json={"sourceUrl": source_url},
                headers=self.headers
            )
            
            logger.info(f"Check article response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                exists = result.get('exists', False)
                logger.info(f"Article exists check result: {exists}")
                return exists
            
            # Log error response
            if response.status_code >= 400:
                try:
                    error_content = response.json()
                    logger.error(f"Error checking if article exists: {error_content}")
                except Exception:
                    logger.error(f"Error checking if article exists (not JSON): {response.text[:500]}")
            
            return False
        except Exception as e:
            logger.error(f"Error checking if article exists: {e}")
            return False  # Default to false if check fails
    
    def upload_image(self, image_url: str) -> str:
        """
        Uploads an image to the API and returns the new URL.
        
        Args:
            image_url: The URL of the image to upload
            
        Returns:
            The new URL of the uploaded image, or the original URL if upload fails
        """
        try:
            # Download the image from the original URL
            response = requests.get(image_url, stream=True)
            response.raise_for_status()

            # Determine MIME type based on URL file extension
            filename = image_url.split('/')[-1]
            file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
            
            # Map common extensions to MIME types
            mime_types = {
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp',
                'svg': 'image/svg+xml'
            }
            
            # Use the appropriate MIME type or default to image/jpeg
            mime_type = mime_types.get(file_ext, 'image/jpeg')
            
            # API endpoint for image uploads
            url = self.build_url('/images')
            
            files = {'file': (filename, response.content, mime_type)}
            
            # Use session headers but ensure only the API key is included
            headers = {'x-api-key': self.api_key} if self.api_key else {}
            
            logger.info(f"Uploading image from {image_url}")
            api_response = requests.post(url, files=files, headers=headers)
            api_response.raise_for_status()

            # Extract new URL from API response
            new_url = api_response.json().get('url')
            logger.info(f"Image uploaded successfully to {new_url}")
            return new_url
        except RequestException as e:
            logger.error(f"Error uploading image {image_url}: {e}")
            return image_url  # Return original URL if upload fails 