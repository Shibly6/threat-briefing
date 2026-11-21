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

# Shared system prompt (same JSON schema as Gemini)
from src.gemini_engine import SYSTEM_PROMPT

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"  # 30 RPM, 12000 TPM free tier


class GroqEngine:
    """
    Fallback AI engine using Groq API (OpenAI-compatible).
    Used when Gemini is rate-limited or unavailable.
    """

    def __init__(self, config: AppConfig):
        load_dotenv()
        self.config = config
        self.api_key = os.getenv("GROQ_API_KEY")
        self.logger = logging.getLogger(__name__)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze_article(self, article: Dict[str, Any]) -> Optional[AnalyzedArticle]:
        if not self.api_key:
            self.logger.warning("[Groq] GROQ_API_KEY not set. Skipping Groq fallback.")
            return None

        now_utc = format_iso_utc(datetime.now(timezone.utc))
        title = article.get("title", "Untitled")
        content_text = article.get("content_text", "")
        user_content = f"Article Title: {title}\n\nArticle Text:\n{content_text[:3500]}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        for attempt in range(1, self.config.max_retries + 1):
            try:
                time.sleep(3.0)  # Groq is generous — 30 RPM, 3s is safe
                with httpx.Client(timeout=45.0) as client:
                    resp = client.post(GROQ_API_URL, json=payload, headers=headers)

                    if resp.status_code == 429:
                        wait_time = 30.0 * attempt
                        self.logger.warning(
                            f"[Groq] 429 Rate Limit (attempt {attempt}/{self.config.max_retries}). "
                            f"Waiting {wait_time}s..."
                        )
                        time.sleep(wait_time)
                        continue

                    if resp.status_code != 200:
                        self.logger.error(f"[Groq] HTTP {resp.status_code} — {resp.text[:200]}")
                        resp.raise_for_status()

                    response_json = resp.json()
                    raw_text = response_json["choices"][0]["message"]["content"].strip()

                    # Extract JSON safely
                    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                    if not json_match:
                        self.logger.error("[Groq] No JSON object found in response.")
                        return None

                    analysis_data = json.loads(json_match.group(0))

                    self.logger.info(f"[Groq] ✓ Analyzed via Groq ({GROQ_MODEL}): {title[:60]}")
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
                self.logger.error(f"[Groq] Exception on attempt {attempt}: {e}")
                if attempt == self.config.max_retries:
                    return None
                time.sleep(2.0 * attempt)

        return None
