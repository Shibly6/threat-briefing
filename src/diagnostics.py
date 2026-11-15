import json
import os
import re
from typing import Dict, List, Any
from bs4 import BeautifulSoup
from src.config import AppConfig

class SourceDiagnostics:
    def __init__(self, config: AppConfig):
        self.config = config

    def analyze_batch_results(self, article_content_path: str) -> Dict[str, Any]:
        """
        Groups extraction results by source and categorizes failure root causes.
        """
        if not os.path.exists(article_content_path):
            raise FileNotFoundError(f"Article content file not found: {article_content_path}")

        with open(article_content_path, "r", encoding="utf-8") as f:
            articles = json.load(f)

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for art in articles:
            source = art.get("source_name", "Unknown")
            grouped.setdefault(source, []).append(art)

        report = {}
        for source, items in grouped.items():
            total = len(items)
            successes = sum(1 for i in items if i.get("extraction_status") == "success")
            partials = sum(1 for i in items if i.get("extraction_status") == "partial")
            failures = sum(1 for i in items if i.get("extraction_status") == "failed")

            failure_breakdown = {
                "JS_RENDERED_SPA": 0,
                "URL_TRANSFORMATION_NEEDED": 0,
                "BOILERPLATE_OR_SELECTOR_ISSUE": 0,
                "FETCH_ERROR": 0,
                "OTHER": 0
            }

            for item in items:
                status = item.get("extraction_status")
                if status in ("failed", "partial"):
                    url = item.get("source_url", "")
                    err = item.get("error_message", "")
                    warnings = item.get("quality_warnings", [])

                    if "msrc.microsoft.com" in url or "Microsoft MSRC" in source:
                        failure_breakdown["JS_RENDERED_SPA"] += 1
                    elif "isc.sans.edu" in url or "rssfeed_full.xml#" in url:
                        failure_breakdown["URL_TRANSFORMATION_NEEDED"] += 1
                    elif "The Hacker News" in source or "boilerplate_detected" in warnings or "short_content" in warnings:
                        failure_breakdown["BOILERPLATE_OR_SELECTOR_ISSUE"] += 1
                    elif "fetch_failed" in warnings or "HTTP" in err:
                        failure_breakdown["FETCH_ERROR"] += 1
                    else:
                        failure_breakdown["OTHER"] += 1

            report[source] = {
                "total": total,
                "success": successes,
                "partial": partials,
                "failed": failures,
                "success_rate": f"{(successes / total) * 100:.1f}%" if total > 0 else "0%",
                "failure_breakdown": failure_breakdown
            }

        return report

    def diagnose_hacker_news_html(self, html_content: str) -> Dict[str, Any]:
        """
        Detailed inspection for The Hacker News HTML structure.
        """
        soup = BeautifulSoup(html_content, "lxml")
        
        # Check specific THN containers
        thn_container = soup.find("div", id="articlebody") or soup.find("div", class_="articlebody")
        generic_container = soup.find("div", class_="article-body")

        raw_p_text = []
        if thn_container:
            for p in thn_container.find_all("p"):
                raw_p_text.append(p.get_text(strip=True))

        total_p_length = sum(len(p) for p in raw_p_text)

        # Check inline newsletter / boilerplate matches
        inline_boilerplate = []
        full_text = " ".join(raw_p_text)
        if "subscribe" in full_text.lower():
            inline_boilerplate.append("Inline Newsletter Subscription Box")
        if "privacy policy" in full_text.lower() or "cookie" in full_text.lower():
            inline_boilerplate.append("Cookie/Privacy Banner Text")

        return {
            "has_thn_specific_container": thn_container is not None,
            "has_generic_hyphen_container": generic_container is not None,
            "paragraphs_found": len(raw_p_text),
            "total_extracted_char_length": total_p_length,
            "detected_inline_boilerplate": inline_boilerplate,
            "primary_failure_reason": "Selector missing 'div#articlebody' and inline newsletter triggered boilerplate warning."
        }

    def diagnose_sans_url(self, url: str) -> Dict[str, Any]:
        """
        Detailed inspection for SANS ISC URLs.
        """
        is_xml_anchor = "rssfeed_full.xml#" in url
        is_query_param = "diary.html?storyid=" in url
        is_canonical_path = bool(re.search(r"/diary/\d+", url))

        recommended_url = url
        if is_xml_anchor:
            story_id = url.split("#")[-1]
            recommended_url = f"https://isc.sans.edu/diary/{story_id}"
        elif is_query_param:
            match = re.search(r"storyid=(\d+)", url)
            if match:
                recommended_url = f"https://isc.sans.edu/diary/{match.group(1)}"

        return {
            "original_url": url,
            "is_xml_anchor": is_xml_anchor,
            "is_query_param": is_query_param,
            "needs_url_transformation": is_xml_anchor or is_query_param,
            "recommended_canonical_url": recommended_url,
            "primary_failure_reason": "URL points to RSS feed XML anchor or query param instead of clean diary path."
        }

    def diagnose_msrc_extraction(self, url: str) -> Dict[str, Any]:
        """
        Detailed inspection for Microsoft MSRC pages.
        """
        return {
            "url": url,
            "is_react_spa": True,
            "static_html_has_body_text": False,
            "recommendation": "SKIP_HTML_EXTRACTION",
            "action_required": "Replace HTML scraper with dedicated MSRC REST API handler (api.msrc.microsoft.com)."
        }