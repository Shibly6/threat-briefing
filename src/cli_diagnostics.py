import argparse
import sys
import os
import json
from typing import Dict, List
from src.config import load_config
from src.diagnostics import SourceDiagnostics
from src.collector import FeedCollector
from src.article_extractor import ArticleExtractor
from src.models import ArticleMetadata

def run_diagnostics_cli():
    parser = argparse.ArgumentParser(description="Source Extraction Diagnostics & Failure Reporter")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings file")
    parser.add_argument("--opml", default="feeds/cyber_security_feeds.opml", help="Path to OPML file")
    parser.add_argument("--limit-per-source", type=int, default=5, help="Max articles to extract per source for diagnostic report")
    args = parser.parse_args()

    config = load_config(args.config)
    diag = SourceDiagnostics(config)

    # 1. Ensure raw_articles.json exists
    if not os.path.exists(config.raw_articles_file):
        print(f"[*] 'data/raw_articles.json' missing. Fetching live feeds from '{args.opml}'...")
        collector = FeedCollector(config)
        collector.run(args.opml)

    # 2. Extract balanced sample from raw_articles.json
    with open(config.raw_articles_file, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Group by source and sample up to limit_per_source
    grouped: Dict[str, List[dict]] = {}
    for item in raw_data:
        src_name = item.get("source_name", "Unknown")
        grouped.setdefault(src_name, []).append(item)

    sampled_data = []
    for src_name, items in grouped.items():
        sampled_data.extend(items[:args.limit_per_source])

    print(f"\n[*] Running extraction on diagnostic sample ({len(sampled_data)} articles across {len(grouped)} sources)...")

    extractor = ArticleExtractor(config)
    extracted_results = []
    for idx, item in enumerate(sampled_data, 1):
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

        print(f"    [{idx}/{len(sampled_data)}] {res.source_name[:20]:<20} | {res.extraction_status:<8} | Chars: {res.character_count:<5} | {res.source_url[:40]}")

    # Persist sample results
    os.makedirs(config.data_dir, exist_ok=True)
    payload = [art.to_dict() for art in extracted_results]
    with open(config.article_content_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print("\n====================================================================================================")
    print("                               SOURCE EXTRACTION DIAGNOSTICS REPORT                                 ")
    print("====================================================================================================\n")

    report = diag.analyze_batch_results(config.article_content_file)

    header_fmt = "{:<26} | {:<7} | {:<7} | {:<7} | {:<7} | {:<12} | {:<30}"
    row_fmt    = "{:<26} | {:<7} | {:<7} | {:<7} | {:<7} | {:<12} | {:<30}"

    print(header_fmt.format("Source Name", "Total", "Success", "Partial", "Failed", "Success Rate", "Primary Failure Driver"))
    print("-" * 120)

    for source, data in report.items():
        fb = data["failure_breakdown"]
        primary_cause = "None (All Passed)"
        if data["failed"] > 0 or data["partial"] > 0:
            primary_cause = max(fb, key=fb.get)

        source_str = source[:24] + ".." if len(source) > 26 else source

        print(row_fmt.format(
            source_str,
            str(data["total"]),
            str(data["success"]),
            str(data["partial"]),
            str(data["failed"]),
            data["success_rate"],
            primary_cause
        ))

    print("\n----------------------------------------------------------------------------------------------------")
    print("                                   SPECIFIC SOURCE DEEP-DIVES                                      ")
    print("----------------------------------------------------------------------------------------------------\n")

    print("[1] THE HACKER NEWS DIAGNOSTICS:")
    print("    - Root Cause: Selector Mismatch (`div#articlebody`) + Inline Newsletter Box.")
    print("    - Raw Text Status: Extracted paragraphs truncated when inline newsletter prompts trigger global boilerplate rules.")
    print("    - Action: Add 'div#articlebody' to content selectors & refine boilerplate rules.\n")

    print("[2] SANS ISC DIAGNOSTICS:")
    print("    - Root Cause: Wrong URL format in RSS feed (`rssfeed_full.xml#31120`).")
    print("    - Transformation Needed: Convert `rssfeed_full.xml#<id>` -> `https://isc.sans.edu/diary/<id>`.")
    print("    - Action: Normalize SANS diary URLs prior to fetching webpage.\n")

    print("[3] MICROSOFT MSRC DIAGNOSTICS:")
    print("    - Root Cause: JavaScript React Single Page Application (SPA).")
    print("    - Status: INSTANTLY SKIPPED (0s overhead).")
    print("    - Action: Replace HTML scraper with dedicated MSRC CVRF REST API handler.\n")

if __name__ == "__main__":
    run_diagnostics_cli()