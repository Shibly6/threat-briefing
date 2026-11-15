import argparse
import sys
from src.config import load_config
from src.daily_runner import DailyPipelineRunner

def run_daily_cli():
    parser = argparse.ArgumentParser(description="Unified Cyber Threat Intelligence Daily Pipeline")
    parser.add_argument("--opml", default="feeds/cyber_security_feeds.opml", help="Path to OPML file")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings file")
    parser.add_argument("--dry-run", action="store_true", help="Run without live AI API calls")
    parser.add_argument("--test-mode", action="store_true", help="Process limited article sample for fast testing")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    config = load_config(args.config)
    runner = DailyPipelineRunner(
        config=config,
        dry_run=args.dry_run,
        verbose=args.verbose,
        test_mode=args.test_mode
    )

    result = runner.run(opml_path=args.opml)
    if result["status"] != "SUCCESS":
        sys.exit(1)

if __name__ == "__main__":
    run_daily_cli()