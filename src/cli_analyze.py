import argparse
import json
import os
import sys
from typing import List

from src.config import load_config
from src.gemini_engine import GeminiEngine
from src.models import AnalyzedArticle

def run_analysis_cli():
    parser = argparse.ArgumentParser(description="Threat AI Analysis Engine CLI")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings file")
    parser.add_argument("--input", help="Path to deduplicated_articles.json")
    parser.add_argument("--output", help="Path to output analyzed_articles.json")
    parser.add_argument("--limit", type=int, help="Limit maximum articles to analyze")
    parser.add_argument("--dry-run", action="store_true", help="Run simulation mode without consuming API quota")
    args = parser.parse_args()

    config = load_config(args.config)
    input_file = args.input or config.deduplicated_articles_file
    output_file = args.output or config.analyzed_articles_file

    if not os.path.exists(input_file):
        print(f"Error: Input file not found at '{input_file}'. Run deduplication first.", file=sys.stderr)
        sys.exit(1)

    engine = GeminiEngine(config)
    try:
        engine.validate_key(is_dry_run=args.dry_run)
    except ValueError as e:
        print(f"\n[!] Configuration Error: {e}\n", file=sys.stderr)
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if args.limit and args.limit > 0:
        articles = articles[:args.limit]

    mode_label = "[DRY-RUN SIMULATION]" if args.dry_run else "[LIVE AI API]"
    print(f"\n[*] Starting AI Analysis Engine {mode_label} on {len(articles)} articles...\n")

    header_fmt = "{:<45} | {:<12} | {:<10} | {:<12} | {:<15}"
    row_fmt    = "{:<45} | {:<12} | {:<10} | {:<12} | {:<15}"

    print(header_fmt.format("Article Title", "Severity", "Score", "Category", "CVEs Mentioned"))
    print("-" * 105)

    analyzed_results: List[AnalyzedArticle] = []

    for idx, item in enumerate(articles, 1):
        try:
            res = engine.analyze_article(item, is_dry_run=args.dry_run)
            if res is None:
                # Skipped due to status != success
                continue

            analyzed_results.append(res)

            title_str = res.title[:43] + ".." if len(res.title) > 45 else res.title
            cves_str = str(res.cves_mentioned)[:13] + ".." if len(str(res.cves_mentioned)) > 15 else str(res.cves_mentioned)

            print(row_fmt.format(
                title_str,
                res.severity.upper(),
                f"{res.importance_score}/100",
                res.category[:12],
                cves_str
            ))

        except Exception as e:
            print(f"    [!] Error analyzing '{item.get('title', 'Untitled')}': {e}", file=sys.stderr)

    # Save outputs to data/analyzed_articles.json
    os.makedirs(config.data_dir, exist_ok=True)
    payload = [art.to_dict() for art in analyzed_results]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Saved {len(analyzed_results)} analyzed articles to: '{output_file}'\n")

if __name__ == "__main__":
    run_analysis_cli()