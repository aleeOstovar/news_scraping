from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime

class ImageModel(BaseModel):
    """Model for image data."""
    id: str
    url: str
    caption: Optional[str] = None
    type: str = "figure"

class ArticleLinkModel(BaseModel):
    """Model for article link data (before content processing)."""
    link: str
    date: str
    
class ArticleContentModel(BaseModel):
    """Model for article content data."""
    link: str
    date: str
    data: str
    creator: str
    title: str
    thumbnail_image: Optional[str] = None
    
class ArticleFullModel(BaseModel):
    """Model for fully processed article data."""
    title: str
    sourceUrl: str
    sourceDate: str
    creator: str
    thumbnailImage: Optional[str] = None
    content: Dict[str, str]
    imagesUrl: List[ImageModel]
    tags: List[str] = Field(default_factory=list)
    status: str = "draft"  # Default status is draft

class ArticleCheckModel(BaseModel):
    """Model for checking if an article exists."""
    sourceUrl: str
    
class ArticleCheckResponse(BaseModel):
    """Response model for article check."""
    exists: bool 