import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import re
import phonenumbers
from phonenumbers import PhoneNumberFormat

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("utils")

def format_phone_number(phone_number: str, country_code: str = 'US') -> Optional[str]:
    """
    Format a phone number to E.164 format.
    
    Args:
        phone_number: The phone number to format
        country_code: ISO 3166-1 alpha-2 country code (default: 'US')
        
    Returns:
        Formatted phone number in E.164 format or None if invalid
    """
    try:
        parsed = phonenumbers.parse(phone_number, country_code)
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    except Exception as e:
        logger.warning(f"Error formatting phone number {phone_number}: {str(e)}")
        return None

def parse_datetime(dt_str: str) -> Optional[datetime]:
    """
    Parse a datetime string in various formats to a timezone-aware UTC datetime.
    """
    if not dt_str:
        return None
        
    # List of possible datetime formats to try
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO 8601 with timezone
        '%Y-%m-%dT%H:%M:%SZ',      # ISO 8601 without milliseconds
        '%Y-%m-%d %H:%M:%S',       # SQL datetime
        '%Y-%m-%d %H:%M',          # Date and time without seconds
        '%Y-%m-%d',                # Date only
        '%m/%d/%Y %H:%M:%S',       # US format with time
        '%m/%d/%Y',                 # US format date only
        '%d/%m/%Y %H:%M:%S',       # European format with time
        '%d/%m/%Y',                 # European format date only
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(dt_str, fmt)
            # If the datetime is naive, assume it's in local time and convert to UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    
    logger.warning(f"Could not parse datetime string: {dt_str}")
    return None

def validate_email(email: str) -> bool:
    """
    Validate an email address format.
    """
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def sanitize_input(input_str: str) -> str:
    """
    Basic input sanitization to prevent XSS and SQL injection.
    """
    if not input_str:
        return ""
    
    # Remove or escape potentially dangerous characters
    sanitized = input_str.replace('"', '\\"')
    sanitized = sanitized.replace("'", "\\'")
    sanitized = sanitized.replace('<', '&lt;')
    sanitized = sanitized.replace('>', '&gt;')
    
    return sanitized

def deep_merge(dict1: Dict, dict2: Dict) -> Dict:
    """
    Recursively merge two dictionaries.
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
            
    return result

def format_duration(minutes: int) -> str:
    """
    Format a duration in minutes to a human-readable string.
    """
    if minutes < 60:
        return f"{minutes} minutes"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes == 0:
        return f"{hours} hour{'s' if hours > 1 else ''}"
    else:
        return f"{hours} hour{'s' if hours > 1 else ''} {remaining_minutes} minutes"

def get_environment() -> str:
    """
    Get the current environment (development, staging, production).
    """
    return os.getenv('ENVIRONMENT', 'development').lower()

def is_production() -> bool:
    """
    Check if the current environment is production.
    """
    return get_environment() == 'production'

def is_development() -> bool:
    """
    Check if the current environment is development.
    """
    return get_environment() == 'development'

def mask_sensitive_data(data: Union[str, Dict, List], fields_to_mask: List[str] = None) -> Union[str, Dict, List]:
    """
    Mask sensitive data in strings, dictionaries, or lists.
    """
    if fields_to_mask is None:
        fields_to_mask = ['password', 'token', 'api_key', 'secret', 'auth']
    
    if isinstance(data, str):
        # Simple string masking (e.g., for logging)
        for field in fields_to_mask:
            if field.lower() in data.lower():
                return '[REDACTED]'
        return data
    elif isinstance(data, dict):
        # Recursively mask dictionary values
        result = {}
        for key, value in data.items():
            if any(field in str(key).lower() for field in fields_to_mask):
                result[key] = '***MASKED***'
            else:
                result[key] = mask_sensitive_data(value, fields_to_mask)
        return result
    elif isinstance(data, list):
        # Recursively mask list items
        return [mask_sensitive_data(item, fields_to_mask) for item in data]
    else:
        return data

def validate_phone_number(phone_number: str, country_code: str = 'US') -> bool:
    """
    Validate a phone number using Google's libphonenumber.
    
    Args:
        phone_number: The phone number to validate
        country_code: ISO 3166-1 alpha-2 country code (default: 'US')
        
    Returns:
        bool: True if the phone number is valid, False otherwise
    """
    try:
        parsed = phonenumbers.parse(phone_number, country_code)
        return phonenumbers.is_valid_number(parsed)
    except Exception as e:
        logger.debug(f"Error validating phone number {phone_number}: {str(e)}")
        return False

def normalize_phone_number(phone_number: str, country_code: str = 'US') -> Optional[str]:
    """
    Normalize a phone number to E.164 format if valid.
    
    Args:
        phone_number: The phone number to normalize
        country_code: ISO 3166-1 alpha-2 country code (default: 'US')
        
    Returns:
        str: Normalized phone number in E.164 format or None if invalid
    """
    try:
        parsed = phonenumbers.parse(phone_number, country_code)
        if not phonenumbers.is_valid_number(parsed):
            return None
        return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    except Exception as e:
        logger.debug(f"Error normalizing phone number {phone_number}: {str(e)}")
        return None

def generate_reference_id(prefix: str = '') -> str:
    """
    Generate a unique reference ID with an optional prefix.
    
    Args:
        prefix: Optional prefix for the reference ID
        
    Returns:
        str: A unique reference ID
    """
    import uuid
    import time
    
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4().hex)[:8]
    
    if prefix:
        return f"{prefix.upper()}_{timestamp}_{unique_id}"
    return f"{timestamp}_{unique_id}"
