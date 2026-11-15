import hashlib
import re
import time
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Set, Dict, Any
from bs4 import BeautifulSoup, Comment
import httpx

from src.config import AppConfig
from src.models import ExtractedArticle, ArticleMetadata
from src.utils import format_iso_utc, parse_to_utc_datetime

BOILERPLATE_PATTERNS = [
    r"cookie\s+policy", r"accept\s+cookies", r"privacy\s+policy",
    r"subscribe\s+to\s+our\s+newsletter", r"all\s+rights\s+reserved",
    r"sign\s+in\s+to\s+continue", r"subscribe\s+to\s+read"
]

class ArticleExtractor:
    def __init__(self, config: AppConfig):
        self.config = config
        self.seen_content_hashes: Set[str] = set()

    def should_skip_web_scraping(self, article_meta: ArticleMetadata) -> Tuple[bool, str]:
        """
        Determines whether HTML web scraping should be skipped based on diagnostic rules.
        """
        url = article_meta.url.lower()
        source = article_meta.source_name.lower()

        # Rule: MSRC is a React SPA - skip web scraping for dedicated API handler
        if "msrc.microsoft.com" in url or "microsoft msrc" in source:
            return True, "JS React SPA — skipped for dedicated MSRC REST API handler"

        return False, ""

    def fetch_html(self, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        last_error = None
        http_status = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                with httpx.Client(
                    timeout=self.config.extraction_timeout_seconds,
                    follow_redirects=True,
                    max_redirects=self.config.max_redirects
                ) as client:
                    resp = client.get(url, headers=headers)
                    http_status = resp.status_code
                    resp.raise_for_status()
                    return resp.text, http_status, None

            except httpx.HTTPStatusError as e:
                http_status = e.response.status_code
                last_error = f"HTTP {http_status}"
                if http_status in (403, 404):
                    break
            except httpx.TimeoutException:
                last_error = f"Timeout after {self.config.extraction_timeout_seconds}s"
            except httpx.RequestError as e:
                last_error = f"Network error: {str(e)}"

            if attempt < self.config.max_retries:
                time.sleep(0.5 * attempt)

        return None, http_status, last_error

    def extract_from_html(
        self,
        html_content: str,
        source_url: str,
        fallback_title: str = "Untitled",
        fallback_author: Optional[str] = None,
        fallback_date: Optional[str] = None
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str]]:
        soup = BeautifulSoup(html_content, "lxml")

        # 1. Canonical URL
        canonical_link = soup.find("link", rel=lambda x: x and "canonical" in x.lower())
        canonical_url = canonical_link["href"].strip() if canonical_link and canonical_link.has_attr("href") else None

        # 2. Title
        extracted_title = None
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            extracted_title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            extracted_title = soup.title.string.strip()
        elif soup.find("h1"):
            extracted_title = soup.find("h1").get_text(strip=True)

        final_title = extracted_title or fallback_title

        # 3. Author
        extracted_author = None
        meta_author = soup.find("meta", attrs={"name": re.compile(r"^author$", re.I)}) or \
                      soup.find("meta", property="article:author")
        if meta_author and meta_author.get("content"):
            extracted_author = meta_author["content"].strip()
        else:
            byline = soup.find(class_=re.compile(r"author|byline", re.I))
            if byline:
                extracted_author = byline.get_text(strip=True)

        final_author = extracted_author or fallback_author

        # 4. Published Date
        extracted_date = None
        meta_date = soup.find("meta", property=re.compile(r"article:published_time|og:updated_time", re.I)) or \
                    soup.find("meta", attrs={"name": re.compile(r"pubdate|date", re.I)})
        if meta_date and meta_date.get("content"):
            dt = parse_to_utc_datetime(meta_date["content"])
            if dt:
                extracted_date = format_iso_utc(dt)

        final_date = extracted_date or fallback_date

        # 5. Clean Body Extraction (with THN div#articlebody support)
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
            element.decompose()

        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        content_container = (
            soup.find("div", id="articlebody") or
            soup.find("div", class_="articlebody") or
            soup.find("article") or
            soup.find("main") or
            soup.find("div", class_=re.compile(r"article-body|post-content|entry-content|content-main", re.I)) or
            soup.body
        )

        if not content_container:
            content_container = soup

        paragraphs = []
        for p in content_container.find_all(["p", "h2", "h3", "h4", "li"]):
            text = p.get_text(" ", strip=True)
            if len(text) > 15:
                paragraphs.append(text)

        cleaned_text = "\n\n".join(paragraphs)
        return cleaned_text, final_title, final_author, final_date, canonical_url

    def extract_article(self, article_meta: ArticleMetadata) -> ExtractedArticle:
        now_utc = format_iso_utc(datetime.now(timezone.utc))

        # Check skip rules first
        should_skip, skip_reason = self.should_skip_web_scraping(article_meta)
        if should_skip:
            return ExtractedArticle(
                source_url=article_meta.url,
                canonical_url=None,
                guid=article_meta.guid,
                source_name=article_meta.source_name,
                title=article_meta.title,
                author=None,
                published_at_utc=article_meta.published_at_utc,
                content_text="",
                character_count=0,
                word_count=0,
                extraction_status="failed",
                quality_warnings=["skipped_spa"],
                error_message=skip_reason,
                extracted_at_utc=now_utc
            )

        html, http_status, error = self.fetch_html(article_meta.url)

        if not html:
            return ExtractedArticle(
                source_url=article_meta.url,
                canonical_url=None,
                guid=article_meta.guid,
                source_name=article_meta.source_name,
                title=article_meta.title,
                author=None,
                published_at_utc=article_meta.published_at_utc,
                content_text="",
                character_count=0,
                word_count=0,
                extraction_status="failed",
                quality_warnings=["fetch_failed"],
                error_message=error or "Fetch failed",
                extracted_at_utc=now_utc
            )

        body_text, title, author, pub_date, canonical_url = self.extract_from_html(
            html_content=html,
            source_url=article_meta.url,
            fallback_title=article_meta.title,
            fallback_date=article_meta.published_at_utc
        )

        char_len = len(body_text)
        word_count = len(body_text.split())
        quality_warnings: List[str] = []
        status = "success"

        if char_len < self.config.min_article_length_chars:
            quality_warnings.append("short_content")
            status = "partial" if char_len > 50 else "failed"

        for pattern in BOILERPLATE_PATTERNS:
            if re.search(pattern, body_text, re.I):
                quality_warnings.append("boilerplate_detected")
                break

        if body_text:
            content_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
            if content_hash in self.seen_content_hashes:
                quality_warnings.append("duplicate_content")
            else:
                self.seen_content_hashes.add(content_hash)

        return ExtractedArticle(
            source_url=article_meta.url,
            canonical_url=canonical_url,
            guid=article_meta.guid,
            source_name=article_meta.source_name,
            title=title,
            author=author,
            published_at_utc=pub_date,
            content_text=body_text,
            character_count=char_len,
            word_count=word_count,
            extraction_status=status,
            quality_warnings=quality_warnings,
            error_message="None" if status != "failed" else "Extracted text below minimum threshold",
            extracted_at_utc=now_utc
        )