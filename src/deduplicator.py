import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlunparse
from typing import List, Dict, Any, Tuple, Set

from src.config import AppConfig
from src.models import DeduplicationReport
from src.utils import parse_to_utc_datetime, format_iso_utc

class ArticleDeduplicator:
    def __init__(self, config: AppConfig):
        self.config = config

    def normalize_url(self, url: str) -> str:
        """
        Strips tracking query parameters (e.g. utm_*), lowers host, strips trailing slash.
        """
        if not url:
            return ""
        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")

        # Strip tracking parameters
        query_params = parse_qs(parsed.query)
        cleaned_params = {k: v for k, v in query_params.items() if not k.lower().startswith("utm_")}
        cleaned_query = "&".join(f"{k}={v[0]}" for k, v in cleaned_params.items())

        return urlunparse((scheme, netloc, path, parsed.params, cleaned_query, ""))

    def normalize_title(self, title: str) -> str:
        """
        Normalizes title string by stripping punctuation, lowercasing, and collapsing spaces.
        """
        if not title:
            return ""
        cleaned = re.sub(r"[^\w\s]", "", title.lower())
        return " ".join(cleaned.split())

    def get_word_3grams(self, text: str) -> Set[Tuple[str, str, str]]:
        """
        Generates 3-gram word tuples for Jaccard content similarity.
        """
        words = re.findall(r"\b\w+\b", text.lower())
        if len(words) < 3:
            return set(tuple(words))
        return set(zip(words[:-2], words[1:-1], words[2:]))

    def calculate_jaccard_similarity(self, grams_a: Set[Any], grams_b: Set[Any]) -> float:
        """
        Computes Jaccard Similarity J(A, B) = |A ∩ B| / |A ∪ B|
        """
        if not grams_a or not grams_b:
            return 0.0
        intersection = len(grams_a.intersection(grams_b))
        union = len(grams_a.union(grams_b))
        return intersection / union if union > 0 else 0.0

    def is_fresh(self, article: Dict[str, Any], now_utc: datetime) -> bool:
        """
        Checks if article was published within max_article_age_hours.
        """
        pub_date_str = article.get("published_at_utc") or article.get("fetched_at_utc")
        if not pub_date_str:
            return True  # Keep if date unavailable

        dt_pub = parse_to_utc_datetime(pub_date_str)
        if not dt_pub:
            return True

        age_hours = (now_utc - dt_pub).total_seconds() / 3600.0
        return age_hours <= self.config.max_article_age_hours

    def process(self, articles: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], DeduplicationReport]:
        now_utc = datetime.now(timezone.utc)
        report = DeduplicationReport(total_before=len(articles))

        # 1. Freshness Filter
        fresh_articles = []
        for art in articles:
            if self.is_fresh(art, now_utc):
                fresh_articles.append(art)
            else:
                report.removed_by_age += 1

        # Trackers for deduplication
        seen_urls: Set[str] = set()
        seen_guids: Set[str] = set()
        seen_titles: Set[str] = set()
        seen_content_hashes: Set[str] = set()
        seen_3gram_sets: List[Set[Tuple[str, str, str]]] = []

        deduplicated: List[Dict[str, Any]] = []

        for art in fresh_articles:
            raw_url = art.get("source_url") or art.get("url", "")
            canonical_url = art.get("canonical_url", "")
            norm_source_url = self.normalize_url(raw_url)
            norm_canonical_url = self.normalize_url(canonical_url) if canonical_url else ""
            
            guid = art.get("guid", "").strip()
            title = art.get("title", "")
            norm_title = self.normalize_title(title)
            content_text = art.get("content_text", "").strip()

            # 2. URL Check
            if (norm_source_url and norm_source_url in seen_urls) or \
               (norm_canonical_url and norm_canonical_url in seen_urls):
                report.removed_by_url += 1
                continue

            # 3. GUID Check
            if guid and guid in seen_guids:
                report.removed_by_guid += 1
                continue

            # 4. Title Check
            if norm_title and norm_title in seen_titles:
                report.removed_by_title += 1
                continue

            # 5. Content Check (Exact Hash & Jaccard Similarity)
            is_content_duplicate = False
            if content_text and len(content_text) > 100:
                body_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
                if body_hash in seen_content_hashes:
                    is_content_duplicate = True
                else:
                    # Near-duplicate Jaccard 3-gram check
                    grams = self.get_word_3grams(content_text)
                    for existing_grams in seen_3gram_sets:
                        sim = self.calculate_jaccard_similarity(grams, existing_grams)
                        if sim >= self.config.content_similarity_threshold:
                            is_content_duplicate = True
                            break

                    if not is_content_duplicate:
                        seen_content_hashes.add(body_hash)
                        seen_3gram_sets.append(grams)

            if is_content_duplicate:
                report.removed_by_content += 1
                continue

            # If all checks pass, retain article
            if norm_source_url:
                seen_urls.add(norm_source_url)
            if norm_canonical_url:
                seen_urls.add(norm_canonical_url)
            if guid:
                seen_guids.add(guid)
            if norm_title:
                seen_titles.add(norm_title)

            deduplicated.append(art)

        report.final_count = len(deduplicated)
        return deduplicated, report

    def run_pipeline(
        self,
        input_file: str,
        output_file: str
    ) -> Tuple[List[Dict[str, Any]], DeduplicationReport]:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Input file not found: {input_file}")

        with open(input_file, "r", encoding="utf-8") as f:
            articles = json.load(f)

        deduped, report = self.process(articles)

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(deduped, f, indent=2, ensure_ascii=False)

        return deduped, report