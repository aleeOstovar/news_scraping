import logging
import time
from typing import Dict, Any, Optional

import requests
from requests.exceptions import RequestException

from app.config import API_BASE_URL, API_KEY

logger = logging.getLogger(__name__)

class APIClient:
    """
    Client for interacting with the backend API.
    """
    def __init__(
        self, 
        base_url: str = API_BASE_URL, 
        api_key: Optional[str] = API_KEY, 
        max_retries: int = 3
    ):
        """
        Initialize the API client
        
        Args:
            base_url: The base URL of the API
            api_key: API key if required
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.max_retries = max_retries
        self.session = requests.Session()
        
        # Setup headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if api_key:
            self.headers['x-api-key'] = api_key
            
        logger.info(f"Initialized API client for {self.base_url}")
        
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
        endpoint = '/api/v1/news-posts'
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Sending data to {url} (Attempt {attempt + 1}/{self.max_retries})")
                response = self.session.post(
                    url=url,
                    json=data,
                    headers=self.headers
                )
                
                response.raise_for_status()
                logger.info("Successfully sent data to API")
                return response.json()
                
            except RequestException as e:
                logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
                
        raise RequestException("Failed to send data after all retry attempts")
    
    def check_article_exists(self, source_url: str) -> bool:
        """
        Check if an article with the given source URL already exists in the database.
        
        Args:
            source_url: The URL of the article to check
            
        Returns:
            True if the article exists, False otherwise
        """
        endpoint = '/api/v1/news-posts/check'
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.post(
                url=url,
                json={"sourceUrl": source_url},
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('exists', False)
            
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
            endpoint = '/api/v1/images'
            url = f"{self.base_url}{endpoint}"
            
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