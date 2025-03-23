import re
import json
import hmac
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import pytz
from loguru import logger

from app.config import settings


def validate_slack_signature(request_timestamp: str, signature: str, body: str) -> bool:
    """
    Validate that the request is coming from Slack.
    
    Args:
        request_timestamp: X-Slack-Request-Timestamp header
        signature: X-Slack-Signature header
        body: Raw request body
    
    Returns:
        bool: True if the signature is valid
    """
    if not settings.SLACK_SIGNING_SECRET:
        return False
        
    # Check if the timestamp is stale (older than 5 minutes)
    current_timestamp = int(time.time())
    if abs(int(request_timestamp) - current_timestamp) > 60 * 5:
        return False
    
    # Create the signature base string
    sig_basestring = f"v0:{request_timestamp}:{body}"
    
    # Compute the HMAC-SHA256
    req_hash = hmac.new(
        key=settings.SLACK_SIGNING_SECRET.encode(),
        msg=sig_basestring.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    
    # Compare the computed signature with the provided one
    computed_signature = f"v0={req_hash}"
    return hmac.compare_digest(computed_signature, signature)


def validate_twilio_signature(signature: str, url: str, params: Dict[str, Any]) -> bool:
    """
    Validate that the request is coming from Twilio.
    
    Args:
        signature: X-Twilio-Signature header
        url: Full URL of the request
        params: Request params
    
    Returns:
        bool: True if the signature is valid
    """
    from twilio.request_validator import RequestValidator
    
    if not settings.TWILIO_AUTH_TOKEN:
        return False
        
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    return validator.validate(url, params, signature)


def format_currency(value: float, currency: str = "USD") -> str:
    """
    Format a currency value.
    
    Args:
        value: The value to format
        currency: The currency code
    
    Returns:
        str: Formatted currency string
    """
    if currency == "USD":
        return f"${value:,.2f}"
    elif currency == "EUR":
        return f"€{value:,.2f}"
    elif currency == "GBP":
        return f"£{value:,.2f}"
    else:
        return f"{value:,.2f} {currency}"


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """
    Format a percentage value.
    
    Args:
        value: The value to format (e.g., 0.1234 for 12.34%)
        decimal_places: Number of decimal places
    
    Returns:
        str: Formatted percentage string
    """
    return f"{value * 100:.{decimal_places}f}%"


def get_date_range(range_type: str, timezone: str = "UTC") -> tuple:
    """
    Get start and end dates for common date ranges.
    
    Args:
        range_type: "today", "yesterday", "last_7_days", "last_30_days", "this_month", "last_month"
                   or "specific_month_YYYY_MM" for a specific month
        timezone: User's timezone
    
    Returns:
        tuple: (start_date, end_date) in UTC
    """
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    
    if range_type == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    
    elif range_type == "yesterday":
        yesterday = now - timedelta(days=1)
        start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    elif range_type == "last_7_days":
        start_date = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    
    elif range_type == "last_30_days":
        start_date = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    
    elif range_type == "this_month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    
    elif range_type == "last_month":
        last_month = now.replace(day=1) - timedelta(days=1)
        start_date = last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
    
    elif range_type.startswith("specific_month_"):
        # Format: specific_month_YYYY_MM
        try:
            year, month = map(int, range_type.split("_")[2:])
            logger.info(f"Processing specific month: {year}-{month}")
            start_date = datetime(year, month, 1, tzinfo=tz)
            
            # Last day of the month: Get first day of next month and subtract 1 microsecond
            if month == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=tz) - timedelta(microseconds=1)
            else:
                end_date = datetime(year, month + 1, 1, tzinfo=tz) - timedelta(microseconds=1)
                
            logger.info(f"Date range for {range_type}: {start_date} to {end_date}")
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing specific month {range_type}: {e}")
            # If invalid format, default to last 30 days
            start_date = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
    
    else:
        logger.warning(f"Unknown date range type: {range_type}, defaulting to last 7 days")
        # Default to last 7 days if unknown range type
        start_date = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
    
    # Convert to UTC
    return start_date.astimezone(pytz.UTC), end_date.astimezone(pytz.UTC)
def extract_query_intent(text: str) -> Dict[str, Any]:
    """
    Extract the intent and parameters from a user query.
    
    Args:
        text: User query text
    
    Returns:
        dict: Intent and parameters
    """
    # Basic patterns for date ranges
    today_pattern = r"today|today's"
    yesterday_pattern = r"yesterday|yesterday's"
    week_pattern = r"this week|last 7 days|past week|weekly"
    month_pattern = r"this month|current month"  # Fixed: Separated "this month" from "last 30 days"
    last_30_days_pattern = r"last 30 days|past month|past 30 days"
    
    # Add patterns for specific months
    month_names = ["january", "february", "march", "april", "may", "june", 
                  "july", "august", "september", "october", "november", "december"]
    month_aliases = ["jan", "feb", "mar", "apr", "may", "jun", 
                    "jul", "aug", "sep", "oct", "nov", "dec"]
    
    # Pattern for "last month_name" (e.g., "last february", "last feb")
    last_specific_month_pattern = r"last\s+(" + "|".join(month_names + month_aliases) + r")"
    
    # Pattern for just month names (e.g., "february", "feb")
    month_name_pattern = r"\b(" + "|".join(month_names + month_aliases) + r")\b"
    
    # Basic patterns for metrics
    sales_pattern = r"sales|revenue|earnings|income"
    orders_pattern = r"orders|purchases"
    products_pattern = r"products|items|goods"
    customers_pattern = r"customers|buyers|clients"
    
    # Patterns for geographic data
    geo_pattern = r"region|country|location|city|place|area|territory|province|state"
    
    # Patterns for conversion rate
    conversion_pattern = r"conversion|convert|abandonment|checkout"
    
    # Determine time range
    time_range = "last_7_days"  # Default to last 7 days
    
    # Check for specific month patterns first (most specific)
    if re.search(last_specific_month_pattern, text, re.IGNORECASE):
        # Extract the month name
        match = re.search(last_specific_month_pattern, text, re.IGNORECASE)
        month_text = match.group(1).lower()
        # Map month alias to full name if needed
        month_map = dict(zip(month_aliases, range(1, 13)))
        month_map.update(dict(zip(month_names, range(1, 13))))
        
        # Get current date to determine year
        now = datetime.now()
        month_num = month_map.get(month_text)
        
        if month_num:
            # If the requested month is ahead of current month, it's from last year
            year = now.year if month_num <= now.month else now.year - 1
            time_range = f"specific_month_{year}_{month_num:02d}"
            logger.info(f"Detected specific month request: {month_text} -> {time_range}")
    
    # Check for just month names (without "last")
    elif re.search(month_name_pattern, text, re.IGNORECASE):
        match = re.search(month_name_pattern, text, re.IGNORECASE)
        month_text = match.group(1).lower()
        # Map month alias to number
        month_map = dict(zip(month_aliases, range(1, 13)))
        month_map.update(dict(zip(month_names, range(1, 13))))
        
        now = datetime.now()
        month_num = month_map.get(month_text)
        
        if month_num:
            # Assume current year unless the month is in the future
            year = now.year if month_num <= now.month else now.year - 1
            time_range = f"specific_month_{year}_{month_num:02d}"
            logger.info(f"Detected month name: {month_text} -> {time_range}")
    
    # Handle "this month" specifically - map to current calendar month
    elif re.search(month_pattern, text, re.IGNORECASE):
        now = datetime.now()
        time_range = f"specific_month_{now.year}_{now.month:02d}"
        logger.info(f"Detected 'this month' request -> {time_range}")
    
    # Standard time ranges
    elif re.search(today_pattern, text, re.IGNORECASE):
        time_range = "today"
    elif re.search(yesterday_pattern, text, re.IGNORECASE):
        time_range = "yesterday"
    elif re.search(week_pattern, text, re.IGNORECASE):
        time_range = "last_7_days"
    elif re.search(last_30_days_pattern, text, re.IGNORECASE):
        time_range = "last_30_days"
    
    # Determine primary metric
    primary_metric = "sales"
    if re.search(orders_pattern, text, re.IGNORECASE):
        primary_metric = "orders"
    elif re.search(products_pattern, text, re.IGNORECASE):
        primary_metric = "products"
    elif re.search(customers_pattern, text, re.IGNORECASE):
        primary_metric = "customers"
    elif re.search(geo_pattern, text, re.IGNORECASE):
        primary_metric = "geo"
    elif re.search(conversion_pattern, text, re.IGNORECASE):
        primary_metric = "conversion"
    
    # Determine if user is asking for top products
    # FIX: Check for numeric patterns like "top 7" or "top seven" products
    top_products_pattern = r"top\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(products|selling|items|goods)"
    top_match = re.search(top_products_pattern, text.lower())
    
    if top_match:
        # Convert word numbers to digits if needed
        number_word_map = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }
        
        number_str = top_match.group(1)
        if number_str in number_word_map:
            top_n = number_word_map[number_str]
        else:
            try:
                top_n = int(number_str)
            except ValueError:
                top_n = 5  # Default to top 5 if parsing fails
        
        top_products = True
    else:
        # Check generic "top products" phrases
        top_products = any(phrase in text.lower() for phrase in ["top products", "best selling", "best-selling", "best seliing"])
        top_n = 5  # Default to top 5
    
    # Determine if user is asking for bottom products
    bottom_products = any(phrase in text.lower() for phrase in ["worst selling", "lowest", "worst-selling", "poorest performing", "bottom 5", "bottom five"])
    
    # Determine if user is asking for geographic data
    include_geo_data = re.search(geo_pattern, text, re.IGNORECASE) is not None or "where" in text.lower()
    
    # Determine if user is asking for conversion rate
    include_conversion_rate = re.search(conversion_pattern, text, re.IGNORECASE) is not None
    
    # Determine if user is asking for a comparison
    comparison = "compare" in text.lower() or "versus" in text.lower() or " vs " in text.lower()
    
    # Check for specific date range
    specific_start_date = None
    specific_end_date = None
    
    # Example: from 2023-01-01 to 2023-01-31
    date_range_pattern = r"from\s+(\d{4}-\d{1,2}-\d{1,2})\s+to\s+(\d{4}-\d{1,2}-\d{1,2})"
    date_range_match = re.search(date_range_pattern, text)
    if date_range_match:
        specific_start_date = date_range_match.group(1)
        specific_end_date = date_range_match.group(2)
    
    logger.info(f"Extracted intent: time_range={time_range}, metric={primary_metric}, top_products={top_products}, top_n={top_n if top_products else 'N/A'}, bottom_products={bottom_products}, geo={include_geo_data}, conversion={include_conversion_rate}")
    
    return {
        "time_range": time_range,
        "primary_metric": primary_metric,
        "top_products": top_products,  # Boolean flag
        "top_products_count": top_n if top_products else 5,  # Number of top products to show
        "bottom_products": bottom_products,
        "include_geo_data": include_geo_data,
        "include_conversion_rate": include_conversion_rate,
        "comparison": comparison,
        "specific_start_date": specific_start_date,
        "specific_end_date": specific_end_date,
        "raw_query": text
    }