import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

import jdatetime
import pytz

logger = logging.getLogger(__name__)

# Mapping of Persian month names to their numerical values
PERSIAN_MONTHS = {
    'فروردین': 1, 'اردیبهشت': 2, 'خرداد': 3,
    'تیر': 4, 'مرداد': 5, 'شهریور': 6,
    'مهر': 7, 'آبان': 8, 'آذر': 9,
    'دی': 10, 'بهمن': 11, 'اسفند': 12
}

def persian_to_gregorian(persian_date: str) -> Optional[datetime]:
    """
    Convert a Persian date string to a Gregorian datetime object.
    
    Args:
        persian_date: Persian date string (e.g., '۱۴ مرداد ۱۴۰۲')
        
    Returns:
        Datetime object in Gregorian calendar or None if conversion fails
    """
    try:
        # Convert Persian digits to English digits
        persian_digits = '۰۱۲۳۴۵۶۷۸۹'
        english_digits = '0123456789'
        for p, e in zip(persian_digits, english_digits):
            persian_date = persian_date.replace(p, e)
        
        # Extract day, month, and year using regex
        pattern = r'(\d+)\s+([آ-ی]+)\s+(\d+)'
        match = re.search(pattern, persian_date)
        
        if not match:
            logger.warning(f"Could not parse Persian date: {persian_date}")
            return None
            
        day, month_name, year = match.groups()
        
        # Convert month name to number
        if month_name not in PERSIAN_MONTHS:
            logger.warning(f"Unknown Persian month: {month_name}")
            return None
            
        month = PERSIAN_MONTHS[month_name]
        
        # Convert to Gregorian
        jdate = jdatetime.date(int(year), month, int(day))
        gdate = jdate.togregorian()
        
        # Return as datetime with Tehran timezone
        tehran_tz = pytz.timezone('Asia/Tehran')
        return tehran_tz.localize(datetime.combine(gdate, datetime.min.time()))
    except Exception as e:
        logger.error(f"Error converting Persian date '{persian_date}': {e}")
        return None

def extract_date_from_text(text: str) -> Optional[datetime]:
    """
    Extract a date from text using various patterns.
    
    Args:
        text: Text containing a date
        
    Returns:
        Datetime object or None if extraction fails
    """
    if not text:
        return None
        
    # Try common date formats
    formats = [
        '%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y',
        '%B %d, %Y', '%d %B %Y', '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S', '%a, %d %b %Y %H:%M:%S',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    
    # Try to extract a date using regex patterns
    patterns = [
        # YYYY-MM-DD or YYYY/MM/DD
        r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',
        # DD-MM-YYYY or DD/MM/YYYY
        r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})',
        # Month DD, YYYY
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})',
        # DD Month YYYY
        r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                groups = match.groups()
                if len(groups) == 3:
                    if groups[0].isdigit() and int(groups[0]) > 1000:  # YYYY-MM-DD
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                    elif groups[2].isdigit() and int(groups[2]) > 1000:  # DD-MM-YYYY or Month DD, YYYY
                        if groups[0].isdigit():  # DD-MM-YYYY
                            return datetime(int(groups[2]), int(groups[1]), int(groups[0]))
                        else:  # Month DD, YYYY
                            month_names = {
                                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                                'september': 9, 'october': 10, 'november': 11, 'december': 12
                            }
                            month = month_names.get(groups[0].lower())
                            if month:
                                return datetime(int(groups[2]), month, int(groups[1]))
            except (ValueError, IndexError):
                continue
    
    # Check if it's a Persian date
    if any(month in text for month in PERSIAN_MONTHS.keys()):
        return persian_to_gregorian(text)
    
    return None

def get_datetime_range(days_ago: int = 7) -> Tuple[datetime, datetime]:
    """
    Get a datetime range from now to a specified number of days ago.
    
    Args:
        days_ago: Number of days ago to start the range
        
    Returns:
        Tuple of (start_date, end_date)
    """
    end_date = datetime.now(pytz.utc)
    start_date = end_date - timedelta(days=days_ago)
    return start_date, end_date

def format_datetime(dt: datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    Format a datetime object as a string.
    
    Args:
        dt: Datetime object to format
        format_str: Format string
        
    Returns:
        Formatted datetime string
    """
    if not dt:
        return ""
        
    try:
        return dt.strftime(format_str)
    except Exception as e:
        logger.error(f"Error formatting datetime: {e}")
        return ""

def is_recent(dt: datetime, days: int = 7) -> bool:
    """
    Check if a datetime is within a specified number of days from now.
    
    Args:
        dt: Datetime to check
        days: Number of days to consider as recent
        
    Returns:
        True if the datetime is within the specified range, False otherwise
    """
    if not dt:
        return False
        
    # Ensure datetime has timezone info
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
        
    now = datetime.now(pytz.utc)
    delta = now - dt
    
    return delta.days < days 