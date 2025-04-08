import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Optional, Any
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Persian month mapping
PERSIAN_MONTHS = {
    'فروردین': 1,
    'اردیبهشت': 2,
    'خرداد': 3,
    'تیر': 4,
    'مرداد': 5,
    'شهریور': 6,
    'مهر': 7,
    'آبان': 8,
    'آذر': 9,
    'دی': 10,
    'بهمن': 11,
    'اسفند': 12
}

class Settings(BaseSettings):
    # API Configuration
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:3000")
    API_KEY: str = os.getenv("API_KEY")

    # Scheduler Configuration
    SCHEDULER_INTERVAL_HOURS: float = float(os.getenv("SCHEDULER_INTERVAL_HOURS", "2"))
    SCHEDULER_AUTO_START: bool = os.getenv("SCHEDULER_AUTO_START", "true").lower() == "true"
    SCHEDULER_TIMEZONE: str = os.getenv("SCHEDULER_TIMEZONE", "UTC")
    
    # Article Configuration
    ARTICLE_DELAY_SECONDS: int = int(os.getenv("ARTICLE_DELAY_SECONDS", "20"))
    MAX_AGE_DAYS: int = int(os.getenv("MAX_AGE_DAYS", "3"))

    # News Sources - Simple field, not trying to parse as JSON
    ENABLED_SOURCES_STR: str = os.getenv("ENABLED_SOURCES", "mihan_blockchain,arzdigital")

    # User Agent
    USER_AGENT: str = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36")
    
    # Persian month mapping
    PERSIAN_MONTHS: Dict[str, int] = PERSIAN_MONTHS

    # Logging configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Database Configuration
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "news_scraper_db")
    NEWS_COLLECTION_NAME: str = "news_articles"
    
    # News Sources Configuration
    NEWS_SOURCES: Dict[str, Dict[str, Any]] = {
        "mihan_blockchain": {
            "enabled": "mihan_blockchain" in ENABLED_SOURCES_STR.split(","),
            "url": os.getenv("MIHAN_BLOCKCHAIN_URL", "https://mihanblockchain.com/category/news/"),
            "max_age_days": int(os.getenv("MIHAN_BLOCKCHAIN_MAX_AGE_DAYS", "3"))
        },
        "arzdigital": {
            "enabled": "arzdigital" in ENABLED_SOURCES_STR.split(","),
            "url": os.getenv("ARZ_DIGITAL_URL", "https://arzdigital.com/breaking/"),
            "max_age_days": int(os.getenv("ARZ_DIGITAL_MAX_AGE_DAYS", "3"))
        }
    }

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    def get_enabled_sources(self) -> List[str]:
        """Get list of enabled sources from the ENABLED_SOURCES environment variable."""
        if not self.ENABLED_SOURCES_STR:
            return []
        return [s.strip() for s in self.ENABLED_SOURCES_STR.split(",")]
    
    @property
    def log_dir(self) -> Path:
        """Get the log directory path."""
        log_dir = Path(__file__).parent.parent / "logs"
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

# Create and export a singleton instance
settings = Settings()

def get_settings() -> Settings:
    """
    Returns the application settings loaded from environment variables.
    """
    return settings 