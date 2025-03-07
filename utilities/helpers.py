import re
from datetime import datetime

def validate_indian_number(number):
    """Validate Indian phone numbers"""
    pattern = r'^(\+91[\-\s]?)?[6789]\d{9}$'
    return re.match(pattern, number) is not None

def format_currency(amount):
    """Format numbers to Indian currency format"""
    try:
        return f"₹{float(amount):,.2f}"
    except:
        return "₹NA"

def parse_date(date_str):
    """Try multiple date formats for parsing"""
    formats = [
        '%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', 
        '%b %d, %Y', '%d %b %Y'
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None