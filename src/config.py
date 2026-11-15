import json
import os
from dataclasses import dataclass

@dataclass
class AppConfig:
    user_agent: str = "CyberSecurityNewsAgent/1.0"
    timeout_seconds: float = 10.0
    extraction_timeout_seconds: float = 15.0
    max_retries: int = 3
    min_article_length_chars: int = 200
    max_article_age_hours: int = 48
    content_similarity_threshold: float = 0.85
    gemini_model: str = "gemini-3.1-flash-lite"
    max_daily_analysis_limit: int = 50
    respect_robots_txt: bool = True
    max_redirects: int = 5
    stale_feed_threshold_hours: int = 72
    display_timezone: str = "Asia/Dhaka"
    test_mode: bool = False
    test_mode_article_limit: int = 5
    data_dir: str = "data"
    log_dir: str = "logs"
    reports_dir: str = "reports"
    feed_status_file: str = "data/feed_status.json"
    raw_articles_file: str = "data/raw_articles.json"
    article_content_file: str = "data/article_content.json"
    deduplicated_articles_file: str = "data/deduplicated_articles.json"
    analyzed_articles_file: str = "data/analyzed_articles.json"
    enriched_articles_file: str = "data/enriched_articles.json"
    final_articles_file: str = "data/final_articles.json"
    nvd_cache_file: str = "data/nvd_cache.json"
    kev_catalog_file: str = "data/kev_catalog.json"
    run_history_file: str = "data/run_history.json"
    report_output_file: str = "reports/index.html"

def load_config(config_path: str = "config/settings.json") -> AppConfig:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return AppConfig(
                user_agent=data.get("user_agent", "CyberSecurityNewsAgent/1.0"),
                timeout_seconds=float(data.get("timeout_seconds", 10)),
                extraction_timeout_seconds=float(data.get("extraction_timeout_seconds", 15)),
                max_retries=int(data.get("max_retries", 3)),
                min_article_length_chars=int(data.get("min_article_length_chars", 200)),
                max_article_age_hours=int(data.get("max_article_age_hours", 24)),
                content_similarity_threshold=float(data.get("content_similarity_threshold", 0.85)),
                gemini_model=data.get("gemini_model", "gemini-3.6-flash"),
                max_daily_analysis_limit=int(data.get("max_daily_analysis_limit", 30)),
                respect_robots_txt=data.get("respect_robots_txt", True),
                max_redirects=int(data.get("max_redirects", 5)),
                stale_feed_threshold_hours=int(data.get("stale_feed_threshold_hours", 72)),
                display_timezone=data.get("display_timezone", "Asia/Dhaka"),
                test_mode=bool(data.get("test_mode", False)),
                test_mode_article_limit=int(data.get("test_mode_article_limit", 5)),
                data_dir=data.get("data_dir", "data"),
                log_dir=data.get("log_dir", "logs"),
                reports_dir=data.get("reports_dir", "reports"),
                feed_status_file=data.get("feed_status_file", "data/feed_status.json"),
                raw_articles_file=data.get("raw_articles_file", "data/raw_articles.json"),
                article_content_file=data.get("article_content_file", "data/article_content.json"),
                deduplicated_articles_file=data.get("deduplicated_articles_file", "data/deduplicated_articles.json"),
                analyzed_articles_file=data.get("analyzed_articles_file", "data/analyzed_articles.json"),
                enriched_articles_file=data.get("enriched_articles_file", "data/enriched_articles.json"),
                final_articles_file=data.get("final_articles_file", "data/final_articles.json"),
                nvd_cache_file=data.get("nvd_cache_file", "data/nvd_cache.json"),
                kev_catalog_file=data.get("kev_catalog_file", "data/kev_catalog.json"),
                run_history_file=data.get("run_history_file", "data/run_history.json"),
                report_output_file=data.get("report_output_file", "reports/index.html")
            )
    return AppConfig()