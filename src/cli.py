import argparse
import sys
import os
from src.config import load_config
from src.collector import FeedCollector
from src.utils import format_for_display

def run_cli():
    parser = argparse.ArgumentParser(description="Cybersecurity Feed Intelligence Collector CLI")
    parser.add_argument("--opml", default="feeds/cyber_security_feeds.opml", help="Path to OPML file")
    parser.add_argument("--config", default="config/settings.json", help="Path to config file")
    args = parser.parse_args()

    if not os.path.exists(args.opml):
        print(f"Error: OPML file not found: {args.opml}", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)
    collector = FeedCollector(config)

    print(f"\nCollecting feeds from '{args.opml}'...")
    results = collector.run(args.opml)

    # Table Header displaying localized timezone
    tz_label = config.display_timezone
    header_fmt = "{:<24} | {:<12} | {:<14} | {:<28} | {:<25}"
    row_fmt    = "{:<24} | {:<12} | {:<14} | {:<28} | {:<25}"

    print(f"\nReport Timestamp Display: {tz_label}")
    print(header_fmt.format("Feed Name", "Status", "Articles Found", f"Last Published ({tz_label})", "Error"))
    print("-" * 115)

    for res in results:
        local_pub_date = format_for_display(res.last_published_utc, config.display_timezone)
        
        name_str = res.feed_name[:22] + ".." if len(res.feed_name) > 24 else res.feed_name
        pub_str = local_pub_date[:26] + ".." if len(local_pub_date) > 28 else local_pub_date
        err_str = res.error_message[:23] + ".." if len(res.error_message) > 25 else res.error_message

        print(row_fmt.format(
            name_str,
            res.status,
            str(res.articles_found),
            pub_str,
            err_str
        ))

    print(f"\n[+] Saved persistent feed statuses to: {config.feed_status_file}")
    print(f"[+] Saved persistent raw articles to: {config.raw_articles_file}\n")

if __name__ == "__main__":
    run_cli()