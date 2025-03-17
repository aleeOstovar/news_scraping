import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Optional

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:3000")
API_KEY = os.getenv("API_KEY", "fm_d1df97a159b1a94bce1aa98cea350e3ce48d28561695a60a")

# Scheduler Configuration
SCHEDULER_INTERVAL_HOURS = int(os.getenv("SCHEDULER_INTERVAL_HOURS", "2"))
ARTICLE_DELAY_SECONDS = int(os.getenv("ARTICLE_DELAY_SECONDS", "20"))

# News Source Configuration
NEWS_SOURCES = {
    "mihan_blockchain": {
        "enabled": os.getenv("MIHAN_BLOCKCHAIN_ENABLED", "true").lower() == "true",
        "url": os.getenv("MIHAN_BLOCKCHAIN_URL", "https://mihanblockchain.com/category/news/"),
        "max_age_days": int(os.getenv("MIHAN_BLOCKCHAIN_MAX_AGE_DAYS", "8"))
    }
    # Add more news sources here as needed
}

# User agent for requests
USER_AGENT = os.getenv(
    "USER_AGENT", 
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
)

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

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path(__file__).parent.parent / "logs"
os.makedirs(LOG_DIR, exist_ok=True) 