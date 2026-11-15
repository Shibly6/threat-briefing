import argparse
import json
import os
import sys
from typing import List

from src.config import load_config
from src.models import ArticleMetadata, ExtractedArticle
from src.article_extractor import ArticleExtractor

def run_extraction_cli():
    parser = argparse.ArgumentParser(description="Cybersecurity Article Content Extractor CLI")
    parser.add_argument("--url", help="Extract single article by URL")
    parser.add_argument("--batch", action="store_true", help="Extract batch from data/raw_articles.json")
    parser.add_argument("--config", default="config/settings.json", help="Path to configuration file")
    args = parser.parse_args()

    config = load_config(args.config)
    extractor = ArticleExtractor(config)

    if args.url:
        print(f"\n[+] Processing single URL: {args.url}")
        dummy_meta = ArticleMetadata(
            source_name="CLI Single",
            title="Single Article CLI Test",
            url=args.url,
            guid=args.url,
            published_at_utc=None,
            fetched_at_utc=""
        )
        res = extractor.extract_article(dummy_meta)
        
        print(f"\nURL:              {res.source_url}")
        print(f"Status:           {res.extraction_status}")
        print(f"Extracted Chars:  {res.character_count}")
        print(f"Word Count:       {res.word_count}")
        print(f"Title:            {res.title}")
        print(f"Author:           {res.author or 'N/A'}")
        print(f"Canonical URL:    {res.canonical_url or 'N/A'}")
        print(f"Quality Warnings: {res.quality_warnings}")
        print(f"Error:            {res.error_message}\n")
        return

    if args.batch:
        if not os.path.exists(config.raw_articles_file):
            print(f"Error: Raw articles file not found at '{config.raw_articles_file}'. Run feed collection first.", file=sys.stderr)
            sys.exit(1)

        with open(config.raw_articles_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        print(f"\n[+] Loaded {len(raw_data)} articles from '{config.raw_articles_file}'. Extracting content...\n")

        header_fmt = "{:<60} | {:<10} | {:<12} | {:<25}"
        row_fmt    = "{:<60} | {:<10} | {:<12} | {:<25}"

        print(header_fmt.format("Article URL", "Status", "Char Count", "Error / Warning"))
        print("-" * 115)

        extracted_results: List[ExtractedArticle] = []

        for item in raw_data:
            meta = ArticleMetadata(
                source_name=item.get("source_name", "Unknown"),
                title=item.get("title", "Untitled"),
                url=item["url"],
                guid=item.get("guid", item["url"]),
                published_at_utc=item.get("published_at_utc"),
                fetched_at_utc=item.get("fetched_at_utc", "")
            )
            res = extractor.extract_article(meta)
            extracted_results.append(res)

            url_str = res.source_url[:58] + ".." if len(res.source_url) > 60 else res.source_url
            err_str = (res.error_message if res.error_message != "None" else str(res.quality_warnings))[:23]

            print(row_fmt.format(
                url_str,
                res.extraction_status,
                str(res.character_count),
                err_str
            ))

        # Save to persistent data/article_content.json
        os.makedirs(config.data_dir, exist_ok=True)
        payload = [art.to_dict() for art in extracted_results]

        with open(config.article_content_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print(f"\n[+] Saved {len(extracted_results)} extracted articles to '{config.article_content_file}'.\n")
        return

    parser.print_help()

if __name__ == "__main__":
    run_extraction_cli()