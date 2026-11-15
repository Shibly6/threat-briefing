import json
import os
import time
from typing import Dict, Any, Optional
import httpx
from src.config import AppConfig
from src.models import KevCveData

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

class KevEnricher:
    def __init__(self, config: AppConfig):
        self.config = config
        self.kev_catalog: Dict[str, Dict[str, Any]] = self._load_kev_catalog()

    def _load_kev_catalog(self) -> Dict[str, Dict[str, Any]]:
        # Check cached local catalog file first
        if os.path.exists(self.config.kev_catalog_file):
            try:
                # Refresh catalog if older than 24 hours
                file_age_hours = (time.time() - os.path.getmtime(self.config.kev_catalog_file)) / 3600.0
                if file_age_hours < 24.0:
                    with open(self.config.kev_catalog_file, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception:
                pass

        return self.download_and_cache_catalog()

    def download_and_cache_catalog(self) -> Dict[str, Dict[str, Any]]:
        catalog_map = {}
        headers = {"User-Agent": self.config.user_agent}

        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.get(CISA_KEV_URL, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    vulnerabilities = data.get("vulnerabilities", [])
                    for item in vulnerabilities:
                        cve_id = item.get("cveID", "").strip().upper()
                        if cve_id:
                            catalog_map[cve_id] = {
                                "cve_id": cve_id,
                                "is_kev": True,
                                "date_added": item.get("dateAdded", ""),
                                "due_date": item.get("dueDate", ""),
                                "ransomware_associated": item.get("knownRansomwareCampaignUse", "").lower() == "known",
                                "notes": item.get("shortDescription", "")
                            }

                    os.makedirs(os.path.dirname(self.config.kev_catalog_file), exist_ok=True)
                    with open(self.config.kev_catalog_file, "w", encoding="utf-8") as f:
                        json.dump(catalog_map, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return catalog_map

    def check_cve(self, cve_id: str) -> KevCveData:
        cve_id = cve_id.strip().upper()
        if cve_id in self.kev_catalog:
            item = self.kev_catalog[cve_id]
            return KevCveData(**item)

        return KevCveData(cve_id=cve_id, is_kev=False)