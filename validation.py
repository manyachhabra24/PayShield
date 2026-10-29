# PayShield - input validation.
# Error messages never echo the user's input back.

import unicodedata
from urllib.parse import urlparse

MAX_URL_LEN = 2048
MAX_MESSAGE_LEN = 2000


def parse_url_text(url):
    """Parse a URL as TEXT only (we never visit it).
    Adds http:// if no scheme was typed. Raises ValueError if malformed."""
    candidate = url if "://" in url else "http://" + url
    parsed = urlparse(candidate)
    _ = parsed.hostname
    _ = parsed.port  # raises ValueError for an invalid port
    return parsed


def validate_input(data):
    """Returns (cleaned_values, None) on success or (None, error_message)."""
    if not isinstance(data, dict):
        return None, "Invalid request."

    url = data.get("url", "")
    message = data.get("message", "")
    if not isinstance(url, str) or not isinstance(message, str):
        return None, "Invalid request."

    url = url.strip()
    message = message.strip()

    if not url:
        return None, "Please enter the website you plan to pay."
    if len(url) > MAX_URL_LEN:
        return None, "That web address is too long."
    if len(message) > MAX_MESSAGE_LEN:
        return None, f"The message is too long (maximum {MAX_MESSAGE_LEN} characters)."

    # Reject spaces, control characters and invisible "format" characters
    # (for example zero-width spaces, which can hide in pasted links).
    for ch in url:
        if ch.isspace() or unicodedata.category(ch) in ("Cc", "Cf"):
            return None, "A web address cannot contain spaces or hidden characters."

    try:
        parsed = parse_url_text(url)
    except ValueError:
        return None, "That does not look like a valid web address."

    hostname = parsed.hostname
    if parsed.scheme not in ("http", "https"):
        return None, "Only http and https web addresses can be checked."
    if not hostname or "." not in hostname or len(hostname) > 253:
        return None, "That does not look like a valid website address."

    return {"url": url, "message": message}, None