import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Persian month mapping (global for backward compatibility)
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

# class Settings(BaseSettings):
#     # API Configuration
#     API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:3000")
#     API_KEY: str = os.getenv("API_KEY")

#     # Scheduler Configuration
#     SCHEDULER_INTERVAL: int = int(os.getenv("SCHEDULER_INTERVAL", "3600"))
#     SCHEDULER_AUTO_START: bool = os.getenv("SCHEDULER_AUTO_START", "true").lower() == "true"
#     SCHEDULER_TIMEZONE: str = os.getenv("SCHEDULER_TIMEZONE", "UTC")
#     ARTICLE_DELAY_SECONDS: int = int(os.getenv("ARTICLE_DELAY_SECONDS", "20"))

#     # News Sources - Simple field, not trying to parse as JSON
#     ENABLED_SOURCES_STR: str = os.getenv("ENABLED_SOURCES", "mihan_blockchain")

#     # User Agents - Simple field, not trying to parse as JSON
#     USER_AGENTS_STR: str = os.getenv(
#         "USER_AGENTS", 
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
#     )

#     # Persian month mapping
#     PERSIAN_MONTHS: Dict[str, int] = PERSIAN_MONTHS

#     # Logging configuration
#     LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
#     LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
#     # Database Configuration
#     DB_URL: str = os.getenv("DB_URL", "")

#     model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
#     def get_enabled_sources(self) -> List[str]:
#         """Get list of enabled sources from the ENABLED_SOURCES environment variable."""
#         if not self.ENABLED_SOURCES_STR:
#             return []
#         return [s.strip() for s in self.ENABLED_SOURCES_STR.split(",")]
    
#     def get_user_agents(self) -> List[str]:
#         """Get list of user agents from the USER_AGENTS environment variable."""
#         if not self.USER_AGENTS_STR:
#             return []
#         return [a.strip() for a in self.USER_AGENTS_STR.split(",")]

# def get_settings() -> Settings:
#     """
#     Returns the application settings loaded from environment variables.
#     """
#     return Settings()

# For backwards compatibility
NEWS_SOURCES = {
    "mihan_blockchain": {
        "enabled": True,
        "url": os.getenv("MIHAN_BLOCKCHAIN_URL", "https://mihanblockchain.com/category/news/"),
        "max_age_days": int(os.getenv("MIHAN_BLOCKCHAIN_MAX_AGE_DAYS", "3"))
    }
    # Add more news sources here as needed
}

# Legacy global variables (kept for backward compatibility)
API_BASE_URL = os.getenv("API_BASE_URL")
API_KEY = os.getenv("API_KEY")
SCHEDULER_INTERVAL_HOURS = int(os.getenv("SCHEDULER_INTERVAL_HOURS", "2"))
ARTICLE_DELAY_SECONDS = int(os.getenv("ARTICLE_DELAY_SECONDS", "20"))
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path(__file__).parent.parent / "logs"
os.makedirs(LOG_DIR, exist_ok=True) 