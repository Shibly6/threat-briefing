import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx
from dotenv import load_dotenv

from src.config import AppConfig
from src.models import AnalyzedArticle
from src.utils import format_iso_utc
from src.gemini_engine import SYSTEM_PROMPT

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "poolside/laguna-xs-2.1:free"


class OpenRouterEngine:
    """
    3rd-choice AI engine using OpenRouter API (OpenAI-compatible).
    Used when both Gemini and Groq are rate-limited or unavailable.
    """

    def __init__(self, config: AppConfig):
        load_dotenv()
        self.config = config
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.logger = logging.getLogger(__name__)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze_article(self, article: Dict[str, Any]) -> Optional[AnalyzedArticle]:
        if not self.api_key:
            self.logger.warning("[OpenRouter] OPENROUTER_API_KEY not set. Skipping.")
            return None

        now_utc = format_iso_utc(datetime.now(timezone.utc))
        title = article.get("title", "Untitled")
        content_text = article.get("content_text", "")
        user_content = f"Article Title: {title}\n\nArticle Text:\n{content_text[:3500]}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/cyber-news-agent",
            "X-Title": "CyberNewsAgent",
        }
        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        for attempt in range(1, self.config.max_retries + 1):
            try:
                time.sleep(3.0)
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(OPENROUTER_API_URL, json=payload, headers=headers)

                    if resp.status_code == 429:
                        wait_time = 30.0 * attempt
                        self.logger.warning(
                            f"[OpenRouter] 429 Rate Limit (attempt {attempt}/{self.config.max_retries}). "
                            f"Waiting {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue

                    if resp.status_code != 200:
                        self.logger.error(f"[OpenRouter] HTTP {resp.status_code} — {resp.text[:200]}")
                        resp.raise_for_status()

                    response_json = resp.json()
                    raw_text = response_json["choices"][0]["message"]["content"].strip()

                    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                    if not json_match:
                        self.logger.error("[OpenRouter] No JSON object in response.")
                        return None

                    analysis_data = json.loads(json_match.group(0))
                    self.logger.info(f"[OpenRouter] ✓ Analyzed via {OPENROUTER_MODEL}: {title[:60]}")

                    return AnalyzedArticle(
                        source_url=article.get("source_url", ""),
                        canonical_url=article.get("canonical_url"),
                        guid=article.get("guid", ""),
                        source_name=article.get("source_name", "Unknown"),
                        title=title,
                        published_at_utc=article.get("published_at_utc"),
                        summary=analysis_data.get("summary", ""),
                        category=analysis_data.get("category", "General Security"),
                        severity=str(analysis_data.get("severity", "medium")).lower(),
                        affected_vendors=analysis_data.get("affected_vendors", []),
                        affected_products=analysis_data.get("affected_products", []),
                        cves_mentioned=analysis_data.get("cves_mentioned", []),
                        attack_type=analysis_data.get("attack_type", "Unknown"),
                        importance_score=int(analysis_data.get("importance_score", 50)),
                        analyzed_at_utc=now_utc,
                    )

            except Exception as e:
                self.logger.error(f"[OpenRouter] Exception on attempt {attempt}: {e}")
                if attempt == self.config.max_retries:
                    return None
                time.sleep(2.0 * attempt)

        return None
