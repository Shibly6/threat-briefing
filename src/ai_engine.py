"""
ai_engine.py — Unified AI Analysis Engine
==========================================
Manages a 3-provider fallback chain for article analysis:
  1. Gemini      (primary)
  2. Groq        (fallback #1 — instant switch on 429)
  3. OpenRouter  (fallback #2 — last resort)

Smart switching rules:
  - 429 RATE_LIMITED  → switch to next provider immediately (no waiting)
  - 401/403 AUTH_ERROR → skip this provider permanently
  - 5xx SERVER_ERROR  → retry within same provider, then switch
  - bad JSON PARSE_ERROR → switch to next provider
"""

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

# ── Shared system prompt ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert Cybersecurity Intelligence Analyst.
Analyze the provided cybersecurity news article and return ONLY a valid JSON object matching the following schema:

{
  "summary": "Write a concise 1-paragraph technical summary in clear, natural Bangla.",
  "category": "Primary category (e.g., Vulnerability, Ransomware, Data Breach, Threat Actor, Advisory, Espionage, Supply Chain, Malware)",
  "severity": "Severity assessment: 'low', 'medium', 'high', or 'critical'",
  "affected_vendors": ["List of vendor names in English, e.g., Microsoft, Adobe"],
  "affected_products": ["List of affected products in English, e.g., Windows 11, Acrobat Reader"],
  "cves_mentioned": ["List of CVE identifiers, e.g., CVE-2026-1234"],
  "attack_type": "Primary attack technique in English (e.g., Remote Code Execution, Phishing, Zero-Day Exploitation, SQL Injection)",
  "importance_score": 85
}

CRITICAL LANGUAGE RULES:
1. The 'summary' MUST be written in natural, fluent Bangla.
2. ALL technical terms MUST remain in English (e.g., CVE, CVSS, Malware, Ransomware, Threat Actor, Vulnerability, Exploit, Phishing, Botnet, Zero-Day, KEV, NVD).
3. Do NOT translate Vendor names, Company names, or Product names. Keep them in English.
4. Severity MUST be exactly one of: 'low', 'medium', 'high', or 'critical'.
5. Output MUST be valid raw JSON.
"""

# ── Result reason codes ───────────────────────────────────────────────────────
SUCCESS      = "success"
RATE_LIMITED = "rate_limited"   # 429  → switch immediately, no wait
AUTH_ERROR   = "auth_error"     # 401/403 → skip provider permanently
SERVER_ERROR = "server_error"   # 5xx → retry, then switch
PARSE_ERROR  = "parse_error"    # bad JSON → switch


# ── Shared helpers ────────────────────────────────────────────────────────────

def _parse_json(raw_text: str) -> Optional[Dict]:
    """Extract first JSON object from raw LLM text safely."""
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _build_result(article: Dict, data: Dict, now_utc: str, ai_provider: str = "Gemini") -> AnalyzedArticle:
    return AnalyzedArticle(
        source_url=article.get("source_url", ""),
        canonical_url=article.get("canonical_url"),
        guid=article.get("guid", ""),
        source_name=article.get("source_name", "Unknown"),
        title=article.get("title", "Untitled"),
        published_at_utc=article.get("published_at_utc"),
        summary=data.get("summary", ""),
        category=data.get("category", "General Security"),
        severity=str(data.get("severity", "medium")).lower(),
        affected_vendors=data.get("affected_vendors", []),
        affected_products=data.get("affected_products", []),
        cves_mentioned=data.get("cves_mentioned", []),
        attack_type=data.get("attack_type", "Unknown"),
        importance_score=int(data.get("importance_score", 50)),
        analyzed_at_utc=now_utc,
        ai_provider=ai_provider,
    )


# ── Provider #1: Google Gemini ────────────────────────────────────────────────

def _call_gemini(api_key: str, model: str, user_content: str,
                 max_retries: int, logger: logging.Logger) -> tuple:
    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_content}"}]}],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2},
    }

    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(4.0)  # ~15 RPM safe
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(endpoint, json=payload,
                                   headers={"Content-Type": "application/json"})

                if resp.status_code == 429:
                    logger.warning(f"[Gemini] 429 on attempt {attempt} → switching provider.")
                    return None, RATE_LIMITED

                if resp.status_code in (401, 403):
                    logger.error(f"[Gemini] Auth error {resp.status_code}.")
                    return None, AUTH_ERROR

                if resp.status_code >= 500:
                    logger.warning(f"[Gemini] Server error {resp.status_code}, retrying...")
                    time.sleep(5.0 * attempt)
                    continue

                if resp.status_code != 200:
                    logger.error(f"[Gemini] HTTP {resp.status_code} — {resp.text[:200]}")
                    return None, SERVER_ERROR

                candidates = resp.json().get("candidates", [])
                if not candidates:
                    logger.warning("[Gemini] Empty candidates.")
                    return None, PARSE_ERROR

                data = _parse_json(candidates[0]["content"]["parts"][0]["text"].strip())
                if not data:
                    logger.warning("[Gemini] JSON parse failed.")
                    return None, PARSE_ERROR

                logger.info("[Gemini ✓] Analyzed successfully.")
                return data, SUCCESS

        except Exception as e:
            logger.error(f"[Gemini] Exception attempt {attempt}: {e}")
            if attempt == max_retries:
                return None, SERVER_ERROR
            time.sleep(2.0 * attempt)

    return None, SERVER_ERROR


# ── Provider #2: Groq ─────────────────────────────────────────────────────────

def _call_groq(api_key: str, user_content: str,
               max_retries: int, logger: logging.Logger) -> tuple:
    payload = {
        "model": "llama-3.3-70b-versatile",   # 30 RPM, 12K TPM free tier
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(3.0)  # 30 RPM → 3s safe
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload, headers=headers
                )

                if resp.status_code == 429:
                    logger.warning(f"[Groq] 429 on attempt {attempt} → switching provider.")
                    return None, RATE_LIMITED

                if resp.status_code in (401, 403):
                    logger.error(f"[Groq] Auth error {resp.status_code}.")
                    return None, AUTH_ERROR

                if resp.status_code >= 500:
                    time.sleep(5.0 * attempt)
                    continue

                if resp.status_code != 200:
                    logger.error(f"[Groq] HTTP {resp.status_code} — {resp.text[:200]}")
                    return None, SERVER_ERROR

                data = _parse_json(resp.json()["choices"][0]["message"]["content"].strip())
                if not data:
                    logger.warning("[Groq] JSON parse failed.")
                    return None, PARSE_ERROR

                logger.info("[Groq ✓] Analyzed successfully.")
                return data, SUCCESS

        except Exception as e:
            logger.error(f"[Groq] Exception attempt {attempt}: {e}")
            if attempt == max_retries:
                return None, SERVER_ERROR
            time.sleep(2.0 * attempt)

    return None, SERVER_ERROR


# ── Provider #3: OpenRouter ───────────────────────────────────────────────────

def _call_openrouter(api_key: str, user_content: str,
                     max_retries: int, logger: logging.Logger) -> tuple:
    payload = {
        "model": "poolside/laguna-xs-2.1:free",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/cyber-news-agent",
        "X-Title": "CyberNewsAgent",
    }

    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(3.0)
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload, headers=headers
                )

                if resp.status_code == 429:
                    wait = 30.0 * attempt
                    logger.warning(f"[OpenRouter] 429 attempt {attempt}, waiting {wait}s...")
                    time.sleep(wait)
                    continue

                if resp.status_code in (401, 403):
                    logger.error(f"[OpenRouter] Auth error {resp.status_code}.")
                    return None, AUTH_ERROR

                if resp.status_code >= 500:
                    time.sleep(5.0 * attempt)
                    continue

                if resp.status_code != 200:
                    logger.error(f"[OpenRouter] HTTP {resp.status_code} — {resp.text[:200]}")
                    return None, SERVER_ERROR

                data = _parse_json(resp.json()["choices"][0]["message"]["content"].strip())
                if not data:
                    logger.warning("[OpenRouter] JSON parse failed.")
                    return None, PARSE_ERROR

                logger.info("[OpenRouter ✓] Analyzed successfully.")
                return data, SUCCESS

        except Exception as e:
            logger.error(f"[OpenRouter] Exception attempt {attempt}: {e}")
            if attempt == max_retries:
                return None, SERVER_ERROR
            time.sleep(2.0 * attempt)

    return None, SERVER_ERROR


# ── AIEngine — Main dispatcher ────────────────────────────────────────────────

class AIEngine:
    """
    Unified AI analysis engine with smart 3-provider fallback chain.

    Provider priority: Gemini → Groq → OpenRouter
    Any provider without an API key is automatically skipped.
    """

    def __init__(self, config: AppConfig, api_key: Optional[str] = None):
        load_dotenv()
        self.config = config
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.gemini_key    = self.api_key
        self.groq_key      = os.getenv("GROQ_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.logger = logging.getLogger(__name__)
        self.stats: Dict[str, int] = {}

    def validate_key(self, is_dry_run: bool = False):
        if not is_dry_run and not (self.gemini_key or self.groq_key or self.openrouter_key):
            raise ValueError(
                "GEMINI_API_KEY is missing! "
                "Please set GEMINI_API_KEY in your environment or in a .env file."
            )

    def analyze_article(self, article: Dict[str, Any], is_dry_run: bool = False) -> Optional[AnalyzedArticle]:
        now_utc = format_iso_utc(datetime.now(timezone.utc))
        status = article.get("extraction_status")
        content_text = article.get("content_text", "")

        if status not in ("success", "partial") or len(content_text) < 20:
            return None

        title = article.get("title", "Untitled")

        # ── Dry-run mode ──────────────────────────────────────────────
        if is_dry_run:
            self.stats["DryRun"] = self.stats.get("DryRun", 0) + 1
            return AnalyzedArticle(
                source_url=article.get("source_url", ""),
                canonical_url=article.get("canonical_url"),
                guid=article.get("guid", ""),
                source_name=article.get("source_name", "DryRun Source"),
                title=title,
                published_at_utc=article.get("published_at_utc"),
                summary=f"[ড্রাই-রান সিমুলেশন] '{title}' নিবন্ধের কারিগরি বিবরণ। Zero-Day Vulnerability সফলভাবে শনাক্ত করা হয়েছে।",
                category="Vulnerability",
                severity="high",
                affected_vendors=["Microsoft"],
                affected_products=["Windows 11"],
                cves_mentioned=["CVE-2026-0001"],
                attack_type="Remote Code Execution",
                importance_score=80,
                analyzed_at_utc=now_utc,
                ai_provider="DryRun",
            )

        user_content = f"Article Title: {title}\n\nArticle Text:\n{content_text[:3500]}"
        model_name = os.getenv("GEMINI_MODEL", self.config.gemini_model)

        # ── Build active provider chain ───────────────────────────────
        providers = []
        if self.gemini_key:
            providers.append(("Gemini", lambda: _call_gemini(
                self.gemini_key, model_name, user_content,
                self.config.max_retries, self.logger
            )))
        if self.groq_key:
            providers.append(("Groq", lambda: _call_groq(
                self.groq_key, user_content,
                self.config.max_retries, self.logger
            )))
        if self.openrouter_key:
            providers.append(("OpenRouter", lambda: _call_openrouter(
                self.openrouter_key, user_content,
                self.config.max_retries, self.logger
            )))

        if not providers:
            self.logger.error("[AIEngine] No API keys configured. Cannot analyze.")
            return None

        # ── Dispatch with smart switching ─────────────────────────────
        for name, call_fn in providers:
            self.logger.info(f"[AIEngine] Provider: {name} | {title[:50]}")
            data, reason = call_fn()

            if reason == SUCCESS and data:
                self.stats[name] = self.stats.get(name, 0) + 1
                return _build_result(article, data, now_utc, ai_provider=name)

            if reason == AUTH_ERROR:
                self.logger.error(f"[AIEngine] {name} auth error — skipping permanently.")
                continue

            if reason == RATE_LIMITED:
                self.logger.warning(f"[AIEngine] {name} rate-limited → next provider instantly.")
                continue

            self.logger.warning(f"[AIEngine] {name} failed ({reason}) → trying next.")

        self.logger.error(f"[AIEngine] All providers exhausted. Skipped: {title[:60]}")
        return None


# ── Backward-compatibility alias ──────────────────────────────────────────────
# daily_runner.py uses GeminiEngine — this keeps it working without any changes.
GeminiEngine = AIEngine
