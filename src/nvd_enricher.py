import json
import os
import time
from typing import Dict, Any, Optional
import httpx
from src.config import AppConfig
from src.models import NvdCveData

class NvdEnricher:
    def __init__(self, config: AppConfig):
        self.config = config
        self.cache: Dict[str, Dict[str, Any]] = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.config.nvd_cache_file):
            try:
                with open(self.config.nvd_cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_cache(self):
        os.makedirs(os.path.dirname(self.config.nvd_cache_file), exist_ok=True)
        with open(self.config.nvd_cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)

    def fetch_cve_details(self, cve_id: str) -> NvdCveData:
        cve_id = cve_id.strip().upper()

        # Return cached response if available
        if cve_id in self.cache:
            data = self.cache[cve_id]
            return NvdCveData(**data)

        endpoint = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
        headers = {"User-Agent": self.config.user_agent}

        cvss_score = 0.0
        cvss_severity = "UNKNOWN"
        vendor = "Unknown"
        product = "Unknown"
        description = ""

        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(endpoint, headers=headers)
                if resp.status_code == 200:
                    payload = resp.json()
                    vulnerabilities = payload.get("vulnerabilities", [])
                    if vulnerabilities:
                        cve_item = vulnerabilities[0].get("cve", {})
                        
                        # Extract description
                        descriptions = cve_item.get("descriptions", [])
                        for d in descriptions:
                            if d.get("lang") == "en":
                                description = d.get("value", "")
                                break

                        # Extract CVSS Metrics
                        metrics = cve_item.get("metrics", {})
                        cvss_v31 = metrics.get("cvssMetricV31", []) or metrics.get("cvssMetricV30", [])
                        if cvss_v31:
                            data = cvss_v31[0].get("cvssData", {})
                            cvss_score = float(data.get("baseScore", 0.0))
                            cvss_severity = data.get("baseSeverity", "UNKNOWN").upper()

                        # Extract Vendor/Product configurations
                        configs = cve_item.get("configurations", [])
                        if configs:
                            nodes = configs[0].get("nodes", [])
                            if nodes:
                                cpe_matches = nodes[0].get("cpeMatch", [])
                                if cpe_matches:
                                    cpe_str = cpe_matches[0].get("criteria", "")
                                    parts = cpe_str.split(":")
                                    if len(parts) >= 5:
                                        vendor = parts[3].capitalize()
                                        product = parts[4].capitalize()
                time.sleep(0.6)  # Rate limiting polite delay for NVD
        except Exception:
            pass  # Fallback gracefully to default unknown structure on network error

        nvd_obj = NvdCveData(
            cve_id=cve_id,
            cvss_score=cvss_score,
            cvss_severity=cvss_severity,
            vendor=vendor,
            product=product,
            nvd_description=description
        )

        self.cache[cve_id] = nvd_obj.to_dict()
        self._save_cache()
        return nvd_obj