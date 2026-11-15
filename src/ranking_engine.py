from datetime import datetime, timezone
from typing import List, Dict, Any
from src.config import AppConfig
from src.models import EnrichedArticle
from src.utils import parse_to_utc_datetime

SEVERITY_MULTIPLIERS = {
    "critical": 1.25,
    "high": 1.10,
    "medium": 1.00,
    "low": 0.80
}

class RankingEngine:
    def __init__(self, config: AppConfig):
        self.config = config

    def calculate_score(
        self,
        base_score: int,
        severity: str,
        max_cvss: float,
        has_kev_match: bool,
        published_at_utc: str
    ) -> int:
        score = float(base_score)

        # 1. Severity Multiplier
        mult = SEVERITY_MULTIPLIERS.get(severity.lower(), 1.0)
        score *= mult

        # 2. CVSS Score Boost
        if max_cvss >= 9.0:
            score += 15.0
        elif max_cvss >= 7.0:
            score += 10.0
        elif max_cvss >= 4.0:
            score += 5.0

        # 3. KEV Match Boost
        if has_kev_match:
            score += 25.0

        # 4. Recency Boost
        dt_pub = parse_to_utc_datetime(published_at_utc)
        if dt_pub:
            now_utc = datetime.now(timezone.utc)
            hours_old = (now_utc - dt_pub).total_seconds() / 3600.0
            if hours_old <= 12.0:
                score += 10.0
            elif hours_old <= 24.0:
                score += 5.0

        # Bound score between 0 and 100
        return max(0, min(100, int(round(score))))

    def rank_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ranked_list = []

        for art in articles:
            base_score = int(art.get("importance_score", 50))
            severity = str(art.get("severity", "medium")).lower()
            max_cvss = float(art.get("max_cvss_score", 0.0))
            has_kev = bool(art.get("has_kev_match", False))
            pub_date = art.get("published_at_utc", "")

            final_score = self.calculate_score(base_score, severity, max_cvss, has_kev, pub_date)
            art["base_importance_score"] = base_score
            art["final_importance_score"] = final_score
            ranked_list.append(art)

        # Deterministic sorting: final_importance_score DESC, then max_cvss DESC, then title ASC
        return sorted(
            ranked_list,
            key=lambda x: (x["final_importance_score"], x.get("max_cvss_score", 0.0), x.get("title", "")),
            reverse=True
        )