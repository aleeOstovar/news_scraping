import base64
import io
import logging
import re
import requests
from typing import Optional, Tuple, List, Dict, Any
from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def is_data_url(url: str) -> bool:
    """
    Check if a URL is a data URL (base64 encoded image).
    
    Args:
        url: The URL to check
        
    Returns:
        True if the URL is a data URL, False otherwise
    """
    return url.startswith('data:image/')

def extract_from_data_url(data_url: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Extract binary data and content type from a data URL.
    
    Args:
        data_url: The data URL to extract from
        
    Returns:
        Tuple of (binary data, content type) or (None, None) if extraction fails
    """
    try:
        pattern = r'data:image/([a-zA-Z]+);base64,(.+)'
        match = re.match(pattern, data_url)
        
        if not match:
            return None, None
            
        img_format, base64_data = match.groups()
        image_data = base64.b64decode(base64_data)
        return image_data, img_format
    except Exception as e:
        logger.error(f"Error extracting data from data URL: {e}")
        return None, None

def download_image(url: str, timeout: int = 10) -> Optional[bytes]:
    """
    Download an image from a URL.
    
    Args:
        url: The URL to download from
        timeout: Request timeout in seconds
        
    Returns:
        The image data as bytes, or None if download fails
    """
    if is_data_url(url):
        image_data, _ = extract_from_data_url(url)
        return image_data
        
    try:
        # Use a random user agent for the request
        headers = {
            "User-Agent": settings.get_random_user_agent()
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Error downloading image from {url}: {e}")
        return None

def compress_image(image_data: bytes, max_size: int = 1024, 
                  quality: int = 85, format: str = 'JPEG') -> Optional[bytes]:
    """
    Compress an image to reduce its file size.
    
    Args:
        image_data: The image data as bytes
        max_size: Maximum dimension (width or height) in pixels
        quality: JPEG quality (0-100)
        format: Output format ('JPEG', 'PNG', etc.)
        
    Returns:
        Compressed image data as bytes, or None if compression fails
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if image has alpha channel (for JPEG)
        if format == 'JPEG' and img.mode == 'RGBA':
            img = img.convert('RGB')
            
        # Resize if necessary
        width, height = img.size
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
                
            img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Save to bytes
        output = io.BytesIO()
        img.save(output, format=format, quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Error compressing image: {e}")
        return None

def get_image_dimensions(image_data: bytes) -> Tuple[Optional[int], Optional[int]]:
    """
    Get the dimensions of an image.
    
    Args:
        image_data: The image data as bytes
        
    Returns:
        Tuple of (width, height) or (None, None) if getting dimensions fails
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        return img.size
    except Exception as e:
        logger.error(f"Error getting image dimensions: {e}")
        return None, None

def save_image_locally(image_data: bytes, filename: str) -> bool:
    """
    Save an image to the local filesystem.
    
    Args:
        image_data: The image data as bytes
        filename: The filename to save to
        
    Returns:
        True if the image was saved successfully, False otherwise
    """
    try:
        with open(filename, 'wb') as f:
            f.write(image_data)
        return True
    except Exception as e:
        logger.error(f"Error saving image to {filename}: {e}")
        return False 