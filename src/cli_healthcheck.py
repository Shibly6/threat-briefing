import argparse
import sys
from src.config import load_config
from src.healthcheck import HealthChecker

def run_healthcheck_cli():
    parser = argparse.ArgumentParser(description="Cyber Threat Intelligence System Health Checker")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings file")
    args = parser.parse_args()

    config = load_config(args.config)
    checker = HealthChecker(config)
    res = checker.run_diagnostics()

    print("\n========================================================")
    print("      CYBER NEWS INTELLIGENCE AGENT HEALTH CHECK        ")
    print("========================================================")
    for check_name, status in res["checks"].items():
        symbol = "✅ PASS" if status else "❌ FAIL"
        print(f" {check_name:<35} : {symbol}")
    print("--------------------------------------------------------")
    
    if res["all_systems_go"]:
        print(" [+] SYSTEM STATUS: ALL SYSTEMS GO (READY FOR DAILY RUN)\n")
    else:
        print(" [!] SYSTEM STATUS: HEALTH CHECK FAILED. FIX ERRORS ABOVE.\n", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run_healthcheck_cli()