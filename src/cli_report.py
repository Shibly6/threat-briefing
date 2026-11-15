import argparse
import os
import sys

from src.config import load_config
from src.report_generator import ReportGenerator

def run_report_cli():
    parser = argparse.ArgumentParser(description="HTML Intelligence Report Generator CLI")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings file")
    parser.add_argument("--input", help="Path to analyzed_articles.json")
    parser.add_argument("--output", help="Path to output index.html")
    args = parser.parse_args()

    config = load_config(args.config)
    input_file = args.input or config.analyzed_articles_file
    output_file = args.output or config.report_output_file

    if not os.path.exists(input_file):
        print(f"Error: Analyzed articles file not found at '{input_file}'. Run AI analysis first.", file=sys.stderr)
        sys.exit(1)

    print(f"\n[*] Generating HTML Report from '{input_file}'...")
    generator = ReportGenerator(config)

    generated_path = generator.generate_html_report(
        analyzed_articles_path=input_file,
        output_path=output_file
    )

    print(f"[+] Report generated successfully!")
    print(f"[+] Output File: {os.path.abspath(generated_path)}\n")

if __name__ == "__main__":
    run_report_cli()