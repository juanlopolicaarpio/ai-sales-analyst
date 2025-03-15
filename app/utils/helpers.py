import re
import json
import hmac
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
import pytz

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
    
    else:
        raise ValueError(f"Unknown date range type: {range_type}")
    
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
    month_pattern = r"this month|last 30 days|past month|monthly"
    
    # Basic patterns for metrics
    sales_pattern = r"sales|revenue|earnings|income"
    orders_pattern = r"orders|purchases"
    products_pattern = r"products|items|goods"
    customers_pattern = r"customers|buyers|clients"
    
    # Determine time range
    time_range = "today"
    if re.search(yesterday_pattern, text, re.IGNORECASE):
        time_range = "yesterday"
    elif re.search(week_pattern, text, re.IGNORECASE):
        time_range = "last_7_days"
    elif re.search(month_pattern, text, re.IGNORECASE):
        time_range = "last_30_days"
    
    # Determine primary metric
    primary_metric = "sales"
    if re.search(orders_pattern, text, re.IGNORECASE):
        primary_metric = "orders"
    elif re.search(products_pattern, text, re.IGNORECASE):
        primary_metric = "products"
    elif re.search(customers_pattern, text, re.IGNORECASE):
        primary_metric = "customers"
    
    # Determine if user is asking for top products
    top_products = "top products" in text.lower() or "best selling" in text.lower()
    
    # Determine if user is asking for a comparison
    comparison = "compare" in text.lower() or "versus" in text.lower() or " vs " in text.lower()
    
    return {
        "time_range": time_range,
        "primary_metric": primary_metric,
        "top_products": top_products,
        "comparison": comparison,
        "raw_query": text
    }