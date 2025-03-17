import logging
import re
from typing import List, Optional
import unicodedata
import html

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    
    Args:
        text: The text to clean
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
        
    # Unescape HTML entities
    text = html.unescape(text)
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKC', text)
    
    # Replace multiple whitespace with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove control characters
    text = ''.join(ch for ch in text if unicodedata.category(ch)[0] != 'C')
    
    # Trim whitespace
    text = text.strip()
    
    return text

def extract_keywords(text: str, min_length: int = 3, max_count: int = 10) -> List[str]:
    """
    Extract potential keywords from text.
    
    This is a simple implementation that returns the most frequent words.
    For a production system, consider using NLP libraries like NLTK or spaCy.
    
    Args:
        text: The text to extract keywords from
        min_length: Minimum character length for keywords
        max_count: Maximum number of keywords to return
        
    Returns:
        List of keywords
    """
    if not text:
        return []
        
    # Convert to lowercase and split into words
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Filter out short words and count frequency
    word_counts = {}
    for word in words:
        if len(word) >= min_length:
            word_counts[word] = word_counts.get(word, 0) + 1
    
    # Sort by frequency (descending) and take the top N
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    keywords = [word for word, count in sorted_words[:max_count]]
    
    return keywords

def extract_summary(text: str, max_length: int = 200) -> str:
    """
    Extract a summary from text.
    
    This is a simple implementation that returns the first few sentences.
    For a production system, consider using NLP libraries for better summarization.
    
    Args:
        text: The text to extract a summary from
        max_length: Maximum character length for the summary
        
    Returns:
        Summary text
    """
    if not text:
        return ""
    
    # Clean the text first
    clean = clean_text(text)
    
    # If the text is already short, return it
    if len(clean) <= max_length:
        return clean
    
    # Try to find a sentence boundary near the max_length
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    summary = ""
    
    for sentence in sentences:
        if len(summary + sentence) + 1 <= max_length:
            if summary:
                summary += " "
            summary += sentence
        else:
            break
    
    # If no sentence boundary was found, just truncate
    if not summary:
        summary = clean[:max_length].rsplit(' ', 1)[0] + "..."
    
    return summary

def generate_slug(title: str, max_length: int = 80) -> str:
    """
    Generate a URL-friendly slug from a title.
    
    Args:
        title: The title to convert to a slug
        max_length: Maximum character length for the slug
        
    Returns:
        URL-friendly slug
    """
    if not title:
        return ""
    
    # Convert to lowercase and replace spaces with hyphens
    slug = title.lower()
    
    # Remove special characters
    slug = re.sub(r'[^\w\s-]', '', slug)
    
    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)
    
    # Remove consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Trim hyphens from start and end
    slug = slug.strip('-')
    
    # Truncate if necessary
    if len(slug) > max_length:
        slug = slug[:max_length].rsplit('-', 1)[0]
    
    return slug

def normalize_url(url: str) -> str:
    """
    Normalize a URL to a standard format.
    
    Args:
        url: The URL to normalize
        
    Returns:
        Normalized URL
    """
    if not url:
        return ""
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    # Ensure protocol is present
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    return url

def remove_boilerplate(text: str, boilerplate_phrases: List[str] = None) -> str:
    """
    Remove common boilerplate text from article content.
    
    Args:
        text: The text to clean
        boilerplate_phrases: List of phrases to remove
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    if not boilerplate_phrases:
        boilerplate_phrases = [
            "Please enable JavaScript",
            "cookies are disabled",
            "Related Articles",
            "Read more:",
            "Share this article",
            "Copyright ©",
            "All rights reserved",
            "Subscribe to our newsletter",
        ]
    
    clean = text
    for phrase in boilerplate_phrases:
        clean = re.sub(re.escape(phrase), '', clean, flags=re.IGNORECASE)
    
    # Clean up any resulting whitespace issues
    clean = re.sub(r'\s+', ' ', clean)
    clean = clean.strip()
    
    return clean 