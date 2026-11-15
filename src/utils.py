import hashlib
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime

def parse_to_utc_datetime(date_str: Optional[str], time_tuple=None) -> Optional[datetime]:
    """
    Parses various RSS/Atom date formats into a standard UTC datetime object.
    """
    if time_tuple:
        try:
            return datetime(*time_tuple[:6], tzinfo=timezone.utc)
        except Exception:
            pass

    if not date_str:
        return None

    date_str = date_str.strip()

    # Try RFC 822 / RFC 2822
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # Try ISO 8601
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    return None

def format_iso_utc(dt: Optional[datetime]) -> Optional[str]:
    """
    Formats a datetime object to ISO-8601 UTC string (YYYY-MM-DDTHH:MM:SSZ).
    """
    if dt is None:
        return None
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

def format_for_display(iso_utc_str: Optional[str], tz_name: str = "Asia/Dhaka") -> str:
    """
    Converts ISO UTC timestamp string to localized display string in target timezone.
    """
    if not iso_utc_str:
        return "N/A"
    try:
        dt_utc = datetime.fromisoformat(iso_utc_str.replace("Z", "+00:00"))
        local_tz = ZoneInfo(tz_name)
        dt_local = dt_utc.astimezone(local_tz)
        return dt_local.strftime("%Y-%m-%d %I:%M %p %Z")
    except Exception:
        return iso_utc_str

def generate_deterministic_guid(source_name: str, url: str, title: str) -> str:
    """
    Generates a deterministic fallback GUID if missing from feed entry.
    """
    raw_key = f"{source_name.strip().lower()}|{url.strip().lower()}|{title.strip().lower()}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()