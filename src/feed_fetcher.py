from datetime import datetime, timezone
import importlib.util
import importlib
import httpx
from typing import Optional
from src.config import AppConfig

spec = importlib.util.find_spec("feedparser")
if spec is None:
    raise ImportError("Missing dependency 'feedparser'. Install it with `pip install feedparser`.")
feedparser = importlib.import_module("feedparser")
from src.models import FeedSource, FeedValidationResult, ArticleMetadata
from src.robots import RobotsChecker
from src.utils import parse_to_utc_datetime, format_iso_utc, generate_deterministic_guid

class FeedValidator:
    def __init__(self, config: AppConfig):
        self.config = config
        self.robots_checker = RobotsChecker(config.user_agent, config.timeout_seconds)

    def validate_feed(self, source: FeedSource) -> FeedValidationResult:
        now_dt = datetime.now(timezone.utc)
        now_utc_str = format_iso_utc(now_dt)

        # 1. Robots.txt Check
        if self.config.respect_robots_txt and not self.robots_checker.is_allowed(source.xml_url):
            return FeedValidationResult(
                feed_name=source.name,
                xml_url=source.xml_url,
                status="ROBOTS_DISALLOWED",
                http_status=None,
                articles_found=0,
                last_published_utc=None,
                checked_at_utc=now_utc_str,
                is_stale=False,
                error_message="Access disallowed by host's robots.txt"
            )

        # 2. HTTP Request
        headers = {"User-Agent": self.config.user_agent}
        http_status: Optional[int] = None
        try:
            with httpx.Client(
                timeout=self.config.timeout_seconds,
                follow_redirects=True,
                max_redirects=self.config.max_redirects
            ) as client:
                response = client.get(source.xml_url, headers=headers)
                http_status = response.status_code
                response.raise_for_status()
                raw_content = response.content

        except httpx.TimeoutException:
            return FeedValidationResult(
                feed_name=source.name,
                xml_url=source.xml_url,
                status="TIMEOUT",
                http_status=None,
                articles_found=0,
                last_published_utc=None,
                checked_at_utc=now_utc_str,
                is_stale=False,
                error_message=f"Request timed out after {self.config.timeout_seconds}s"
            )
        except httpx.HTTPStatusError as e:
            return FeedValidationResult(
                feed_name=source.name,
                xml_url=source.xml_url,
                status="HTTP_ERROR",
                http_status=e.response.status_code,
                articles_found=0,
                last_published_utc=None,
                checked_at_utc=now_utc_str,
                is_stale=False,
                error_message=f"HTTP Status {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return FeedValidationResult(
                feed_name=source.name,
                xml_url=source.xml_url,
                status="NETWORK_ERROR",
                http_status=http_status,
                articles_found=0,
                last_published_utc=None,
                checked_at_utc=now_utc_str,
                is_stale=False,
                error_message=str(e)
            )

        # 3. RSS/Atom Parsing
        parsed = feedparser.parse(raw_content)

        if parsed.bozo and isinstance(parsed.bozo_exception, (SyntaxError, Exception)):
            return FeedValidationResult(
                feed_name=source.name,
                xml_url=source.xml_url,
                status="MALFORMED_XML",
                http_status=http_status,
                articles_found=0,
                last_published_utc=None,
                checked_at_utc=now_utc_str,
                is_stale=False,
                error_message=f"XML Parsing Exception: {parsed.bozo_exception}"
            )

        articles = []
        latest_pub_dt: Optional[datetime] = None

        for entry in parsed.entries:
            title = getattr(entry, "title", "Untitled").strip()
            url = getattr(entry, "link", "").strip()

            raw_guid = getattr(entry, "id", None) or getattr(entry, "guid", None)
            guid = raw_guid.strip() if raw_guid else generate_deterministic_guid(source.name, url, title)

            date_str = getattr(entry, "published", None) or getattr(entry, "updated", None)
            parsed_tuple = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            
            dt_pub = parse_to_utc_datetime(date_str, parsed_tuple)
            pub_utc_str = format_iso_utc(dt_pub)

            if dt_pub and (latest_pub_dt is None or dt_pub > latest_pub_dt):
                latest_pub_dt = dt_pub

            category = None
            if hasattr(entry, "tags") and entry.tags:
                category = entry.tags[0].get("term")

            articles.append(
                ArticleMetadata(
                    source_name=source.name,
                    title=title,
                    url=url,
                    guid=guid,
                    published_at_utc=pub_utc_str,
                    fetched_at_utc=now_utc_str,
                    category=category
                )
            )

        # 4. Check Feed Staleness
        is_stale = False
        status = "OK"

        if latest_pub_dt:
            hours_old = (now_dt - latest_pub_dt).total_seconds() / 3600.0
            if hours_old > self.config.stale_feed_threshold_hours:
                is_stale = True
                status = "STALE"
        elif len(articles) == 0:
            status = "EMPTY"

        return FeedValidationResult(
            feed_name=source.name,
            xml_url=source.xml_url,
            status=status,
            http_status=http_status,
            articles_found=len(articles),
            last_published_utc=format_iso_utc(latest_pub_dt),
            checked_at_utc=now_utc_str,
            is_stale=is_stale,
            error_message="None" if status in ("OK", "STALE") else "Feed has no articles",
            articles=articles
        )