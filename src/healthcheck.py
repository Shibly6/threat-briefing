import os
import sys
from typing import Dict, Any, List
from dotenv import load_dotenv
from src.config import AppConfig

class HealthChecker:
    def __init__(self, config: AppConfig):
        load_dotenv()  # Load .env file automatically
        self.config = config

    def run_diagnostics(self) -> Dict[str, Any]:
        checks = {}
        all_passed = True

        # 1. Environment Variable Check
        api_key = os.getenv("GEMINI_API_KEY")
        checks["gemini_api_key_present"] = bool(api_key and len(api_key) > 5)
        if not checks["gemini_api_key_present"]:
            all_passed = False

        # 2. Directory Existence & Write Permissions
        dirs_to_check = [self.config.data_dir, self.config.log_dir, self.config.reports_dir]
        for d in dirs_to_check:
            try:
                os.makedirs(d, exist_ok=True)
                test_file = os.path.join(d, ".write_test")
                with open(test_file, "w") as f:
                    f.write("ok")
                os.remove(test_file)
                checks[f"dir_writable_{d}"] = True
            except Exception:
                checks[f"dir_writable_{d}"] = False
                all_passed = False

        # 3. OPML File Check
        opml_path = "feeds/cyber_security_feeds.opml"
        checks["opml_file_exists"] = os.path.exists(opml_path)
        if not checks["opml_file_exists"]:
            all_passed = False

        return {
            "all_systems_go": all_passed,
            "checks": checks
        }