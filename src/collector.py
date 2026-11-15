import json
import os
from typing import List
from src.config import AppConfig
from src.models import FeedSource, FeedValidationResult, ArticleMetadata
from src.feed_fetcher import FeedValidator
from src.opml_parser import parse_opml

class FeedCollector:
    def __init__(self, config: AppConfig):
        self.config = config
        self.validator = FeedValidator(config)

    def run(self, opml_path: str) -> List[FeedValidationResult]:
        sources: List[FeedSource] = parse_opml(opml_path)
        results: List[FeedValidationResult] = []
        all_articles: List[ArticleMetadata] = []

        for source in sources:
            result = self.validator.validate_feed(source)
            results.append(result)
            all_articles.extend(result.articles)

        self._save_status_records(results)
        self._save_raw_articles(all_articles)

        return results

    def _save_status_records(self, results: List[FeedValidationResult]):
        """
        Saves feed execution statuses strictly ordered by feed name to data/feed_status.json
        """
        os.makedirs(self.config.data_dir, exist_ok=True)
        
        # Deterministic sorting by feed name
        sorted_results = sorted(results, key=lambda x: x.feed_name.lower())
        status_payload = [res.to_status_dict() for res in sorted_results]

        with open(self.config.feed_status_file, "w", encoding="utf-8") as f:
            json.dump(status_payload, f, indent=2, ensure_ascii=False)

    def _save_raw_articles(self, articles: List[ArticleMetadata]):
        """
        Saves raw article metadata to data/raw_articles.json.
        Articles are deterministically ordered by published_at_utc descending, then guid.
        """
        os.makedirs(self.config.data_dir, exist_ok=True)

        # Deterministic sorting for deduplication readiness
        sorted_articles = sorted(
            articles,
            key=lambda x: (x.published_at_utc or "", x.guid),
            reverse=True
        )

        articles_payload = [art.to_dict() for art in sorted_articles]

        with open(self.config.raw_articles_file, "w", encoding="utf-8") as f:
            json.dump(articles_payload, f, indent=2, ensure_ascii=False)