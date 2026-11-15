import argparse
import sys
import os
from src.config import load_config
from src.deduplicator import ArticleDeduplicator

def run_dedupe_cli():
    parser = argparse.ArgumentParser(description="Deterministic Article Deduplication CLI")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings file")
    parser.add_argument("--input", help="Path to input article JSON file")
    parser.add_argument("--output", help="Path to output deduplicated JSON file")
    args = parser.parse_args()

    config = load_config(args.config)
    
    input_file = args.input or config.article_content_file
    if not os.path.exists(input_file):
        input_file = config.raw_articles_file

    output_file = args.output or config.deduplicated_articles_file

    if not os.path.exists(input_file):
        print(f"Error: Input file not found at '{input_file}'. Run collection/extraction first.", file=sys.stderr)
        sys.exit(1)

    print(f"\n[*] Reading input articles from: '{input_file}'")
    deduplicator = ArticleDeduplicator(config)
    
    deduped_articles, report = deduplicator.run_pipeline(
        input_file=input_file,
        output_file=output_file
    )

    print("\n=========================================================")
    print("      DETERMINISTIC DEDUPLICATION & FRESHNESS REPORT      ")
    print("=========================================================")
    print(f" Articles Before Filtering: {report.total_before}")
    print(f" Removed by Max Age ({config.max_article_age_hours}h):   {report.removed_by_age}")
    print(f" Removed by Duplicate URL:  {report.removed_by_url}")
    print(f" Removed by Duplicate GUID: {report.removed_by_guid}")
    print(f" Removed by Duplicate Title:{report.removed_by_title}")
    print(f" Removed by Content Sim:    {report.removed_by_content}")
    print("---------------------------------------------------------")
    print(f" Final Deduplicated Count:  {report.final_count}")
    print("=========================================================\n")

    print(f"[+] Saved deduplicated articles to: '{output_file}'\n")

if __name__ == "__main__":
    run_dedupe_cli()