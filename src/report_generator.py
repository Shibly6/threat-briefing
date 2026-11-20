import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.config import AppConfig
from src.utils import format_iso_utc

SEVERITY_LEVELS = ("critical", "high", "medium", "low")

# Standard Lucide-style SVG vector icons (crisp, lightweight, zero external runtime dependency)
SVG_ICONS = {
    "external_link": (
        '<svg class="external-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>'
        '<polyline points="15 3 21 3 21 9"></polyline>'
        '<line x1="10" y1="14" x2="21" y2="3"></line></svg>'
    ),
    "newspaper": (
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-2 2Zm0 0a2 2 0 0 1-2-2v-9c0-1.1.9-2 2-2h2"/>'
        '<path d="M18 14h-8"/><path d="M15 18h-5"/><path d="M10 6h8v4h-8V6Z"/></svg>'
    ),
    "tag": (
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path>'
        '<line x1="7" y1="7" x2="7.01" y2="7"></line></svg>'
    ),
    "bot": (
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="11" width="18" height="10" rx="2"></rect>'
        '<circle cx="12" cy="5" r="2"></circle>'
        '<path d="M12 7v4"></path>'
        '<line x1="8" y1="16" x2="8" y2="16"></line>'
        '<line x1="16" y1="16" x2="16" y2="16"></line></svg>'
    ),
    "copy": (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
    ),
    "flame": (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 '
        '.5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 3.5z"/>'
        '</svg>'
    ),
    "calendar": (
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>'
        '<line x1="16" y1="2" x2="16" y2="6"></line>'
        '<line x1="8" y1="2" x2="8" y2="6"></line>'
        '<line x1="3" y1="10" x2="21" y2="10"></line></svg>'
    ),
    "arrow_right": (
        '<svg class="archive-arrow-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="5" y1="12" x2="19" y2="12"></line>'
        '<polyline points="12 5 19 12 12 19"></polyline></svg>'
    ),
}


def _normalize_severity(value: Any) -> str:
    """Map arbitrary severity values onto the four supported badge levels."""
    sev = str(value or "medium").strip().lower()
    if sev in SEVERITY_LEVELS:
        return sev
    if sev in ("severe", "urgent", "emergency", "crit"):
        return "critical"
    if sev in ("important", "elevated", "moderate-high"):
        return "high"
    if sev in ("informational", "info", "none", "unknown"):
        return "low"
    return "medium"


def _format_pretty_date(date_str: str) -> str:
    """Format YYYY-MM-DD into '11 Nov 2026' style; fallback to original string."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{dt.day} {dt.strftime('%b %Y')}"
    except ValueError:
        return date_str


class ReportGenerator:
    """Generates modern, user-friendly, responsive HTML Threat Intelligence Reports."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.templates_dir = Path(__file__).parent / "templates"

    def _load_asset_or_template(self, filename: str) -> str:
        """Load CSS, JS or HTML template file from src/templates/."""
        filepath = self.templates_dir / filename
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Template asset not found: {filepath}")

    def generate_html_report(self, analyzed_articles_path: str, output_path: str = None) -> str:
        """Backward compatible helper method for test suites and scripts."""
        return self.generate_daily_and_archive_reports(analyzed_articles_path)

    def generate_daily_and_archive_reports(self, final_articles_path: str) -> str:
        """
        Reads analyzed/final articles, computes metrics, updates the universal search index,
        and generates both the dated daily report (reports/YYYY-MM-DD/index.html) and
        updates the archive homepage (reports/index.html).
        """
        if not os.path.exists(final_articles_path):
            raise FileNotFoundError(f"Final articles file not found: {final_articles_path}")

        with open(final_articles_path, "r", encoding="utf-8") as f:
            articles: List[Dict[str, Any]] = json.load(f)

        now_utc = datetime.now(timezone.utc)
        today_date_str = now_utc.strftime("%Y-%m-%d")
        today_date_pretty = _format_pretty_date(today_date_str)
        _ = format_iso_utc(now_utc)

        reports_dir = self.config.reports_dir
        date_dir = os.path.join(reports_dir, today_date_str)
        os.makedirs(date_dir, exist_ok=True)
        date_report_path = os.path.join(date_dir, "index.html")

        # Ensure assets directory in reports/ for standalone or static hosting
        assets_dir = os.path.join(reports_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        # Load externalized modular assets
        shared_css = self._load_asset_or_template("styles.css")
        interactive_js = self._load_asset_or_template("report.js")
        report_template = self._load_asset_or_template("report_template.html")

        # Copy assets to reports/assets/ for direct linking
        with open(os.path.join(assets_dir, "styles.css"), "w", encoding="utf-8") as f:
            f.write(shared_css)
        with open(os.path.join(assets_dir, "report.js"), "w", encoding="utf-8") as f:
            f.write(interactive_js)

        # Sort articles by importance score descending
        sorted_articles = sorted(
            articles,
            key=lambda x: int(x.get("final_importance_score") or x.get("importance_score") or 0),
            reverse=True,
        )

        # Maintain & write universal cross-report search index
        self._update_search_index(sorted_articles, today_date_str, today_date_pretty)

        # 1. Executive Spotlight (Top 5 Priority News)
        spotlight_items = sorted_articles[:5]
        spotlight_html_list = []
        for idx, item in enumerate(spotlight_items, start=1):
            title = html.escape(item.get("title") or "Untitled")
            url = html.escape(item.get("source_url") or "#")
            score = int(item.get("final_importance_score") or item.get("importance_score") or 50)
            sev = _normalize_severity(item.get("severity"))
            rank_str = f"#{idx:02d}"

            kev_badge = (
                f'<span class="badge badge-kev">{SVG_ICONS["flame"]} KEV</span>'
                if item.get("has_kev_match")
                else ""
            )

            spotlight_html_list.append(
                f'<div class="spotlight-row">'
                f'  <div class="spotlight-left">'
                f'    <span class="spotlight-rank">{rank_str}</span>'
                f'    <a href="{url}" target="_blank" rel="noopener noreferrer" class="spotlight-link" title="{title}">'
                f'      {title} {SVG_ICONS["external_link"]}'
                f'    </a>'
                f'  </div>'
                f'  <div class="spotlight-right">'
                f'    <span class="badge badge-{sev}"><span class="badge-dot"></span>{sev.upper()} ({score}/100)</span>'
                f'    {kev_badge}'
                f'  </div>'
                f'</div>'
            )
        spotlight_html = "\n".join(spotlight_html_list) or (
            '<div class="empty-state">No priority intelligence items surfaced in this cycle.</div>'
        )

        # 2. Telemetry Counts
        total_count = len(sorted_articles)
        severity_counts = {level: 0 for level in SEVERITY_LEVELS}
        for article in sorted_articles:
            severity_counts[_normalize_severity(article.get("severity"))] += 1
        critical_count = severity_counts["critical"]
        high_count = severity_counts["high"]
        kev_match_count = sum(1 for a in sorted_articles if a.get("has_kev_match", False))

        # 3. Main Intelligence Feed (Article Cards)
        cards_html_list = []
        for idx, art in enumerate(sorted_articles, start=1):
            sev = _normalize_severity(art.get("severity"))
            title = html.escape(art.get("title") or "Untitled")
            source_url = html.escape(art.get("source_url") or "#")
            source_name = html.escape(art.get("source_name") or "Unknown Source")
            category = html.escape(art.get("category") or "Security")
            summary_bn = html.escape(art.get("summary_bn") or art.get("summary") or "")
            final_score = int(art.get("final_importance_score") or art.get("importance_score") or 50)
            max_cvss = float(art.get("max_cvss_score") or 0.0)
            ai_provider = html.escape(art.get("ai_provider") or "Gemini")

            has_kev = bool(art.get("has_kev_match"))
            kev_badge = (
                f'<span class="badge badge-kev">{SVG_ICONS["flame"]} CISA KEV EXPLOITED</span>'
                if has_kev
                else ""
            )

            cves_list = art.get("cves_mentioned") or []
            vendors_list = art.get("affected_vendors") or []

            # Technical Tags (Clickable NVD CVE Links, CVSS meter, Vendors)
            tags_html = []
            for cve in cves_list:
                cve_clean = str(cve).strip()
                cve_safe = html.escape(cve_clean)
                nvd_url = f"https://nvd.nist.gov/vuln/detail/{cve_safe}"
                tags_html.append(
                    f'<a href="{nvd_url}" target="_blank" rel="noopener noreferrer" class="tag-cve" title="View {cve_safe} on NIST NVD">'
                    f'{cve_safe} {SVG_ICONS["external_link"]}</a>'
                )

            if max_cvss > 0:
                tags_html.append(f'<span class="tag-cvss">CVSS {max_cvss:.1f}</span>')

            for vendor in vendors_list:
                vendor_safe = html.escape(str(vendor).strip())
                tags_html.append(f'<span class="tag-vendor">Vendor: {vendor_safe}</span>')

            tags_block = (
                f'<div class="technical-tags">{" ".join(tags_html)}</div>'
                if tags_html
                else ""
            )

            card_id = f"art-{idx}"
            summary_id = f"summary-{idx}"

            card = f"""
            <article class="article-card" id="{card_id}" data-severity="{sev}" data-has-kev="{'true' if has_kev else 'false'}" data-cves-count="{len(cves_list)}">
                <div class="article-header">
                    <h2 style="font-size: 1.05rem; font-weight: 600; line-height: 1.45;">
                        <a href="{source_url}" target="_blank" rel="noopener noreferrer" class="article-title-link">
                            {title}
                            {SVG_ICONS["external_link"]}
                        </a>
                    </h2>
                    <div class="badge-group">
                        <span class="badge badge-{sev}"><span class="badge-dot"></span>{sev.upper()} ({final_score}/100)</span>
                        {kev_badge}
                    </div>
                </div>

                <div class="article-meta">
                    <div class="meta-tags-left">
                        <span class="meta-pill">{SVG_ICONS["newspaper"]} <strong>{source_name}</strong></span>
                        <span class="meta-pill">{SVG_ICONS["tag"]} {category}</span>
                        <span class="meta-pill">{SVG_ICONS["bot"]} AI: <strong>{ai_provider}</strong></span>
                    </div>
                    <div class="meta-actions-right">
                        <button class="copy-btn" data-copy-target="{summary_id}" title="Copy Bengali intelligence summary to clipboard">
                            {SVG_ICONS["copy"]} <span>Copy Summary</span>
                        </button>
                    </div>
                </div>

                <div class="article-summary-bn" id="{summary_id}">
                    {summary_bn}
                </div>

                {tags_block}
            </article>
            """
            cards_html_list.append(card)

        articles_cards_html = "\n".join(cards_html_list) or (
            '<div class="empty-state">No threat intelligence articles available in this briefing cycle.</div>'
        )

        # Assemble full HTML document using clean template replacements
        final_html = report_template
        replacements = {
            "{{SHARED_CSS}}": shared_css,
            "{{INTERACTIVE_JS}}": interactive_js,
            "{{REPORT_DATE_ISO}}": today_date_str,
            "{{REPORT_DATE_PRETTY}}": today_date_pretty,
            "{{TOTAL_COUNT}}": str(total_count),
            "{{CRITICAL_COUNT}}": str(critical_count),
            "{{HIGH_COUNT}}": str(high_count),
            "{{KEV_COUNT}}": str(kev_match_count),
            "{{SPOTLIGHT_ITEMS}}": spotlight_html,
            "{{ARTICLE_CARDS}}": articles_cards_html,
        }
        for placeholder, value in replacements.items():
            final_html = final_html.replace(placeholder, value)

        with open(date_report_path, "w", encoding="utf-8") as f:
            f.write(final_html)

        self._generate_archive_homepage()
        return date_report_path

    def _update_search_index(
        self,
        today_articles: List[Dict[str, Any]],
        today_date_str: str,
        today_date_pretty: str,
    ):
        """
        Maintains reports/search_index.json and reports/assets/search_index.js
        containing metadata for all articles across past and present briefings.
        """
        reports_dir = self.config.reports_dir
        index_file = os.path.join(reports_dir, "search_index.json")
        assets_dir = os.path.join(reports_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        existing_index: List[Dict[str, Any]] = []
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    existing_index = json.load(f)
            except Exception:
                existing_index = []

        # If index is empty or has fewer dates than existing folders, backfill from past reports
        indexed_dates = {item.get("date") for item in existing_index if item.get("date")}
        past_dirs = [
            d for d in os.listdir(reports_dir)
            if os.path.isdir(os.path.join(reports_dir, d))
            and d != "assets"
            and d != today_date_str
            and d not in indexed_dates
        ]
        if past_dirs:
            for d in past_dirs:
                p = os.path.join(reports_dir, d, "index.html")
                if os.path.exists(p):
                    existing_index.extend(self._extract_articles_from_html(p, d))

        # Remove any existing entries for today_date_str to avoid duplicates on re-run
        filtered_index = [item for item in existing_index if item.get("date") != today_date_str]

        # Convert today's articles into search index items
        for idx, item in enumerate(today_articles, start=1):
            cves = [str(c).strip() for c in (item.get("cves_mentioned") or [])]
            vendors = [str(v).strip() for v in (item.get("affected_vendors") or [])]
            summary_raw = item.get("summary_bn") or item.get("summary") or ""
            filtered_index.append({
                "id": f"{today_date_str}_art-{idx}",
                "date": today_date_str,
                "date_pretty": today_date_pretty,
                "title": item.get("title") or "Untitled",
                "source_url": item.get("source_url") or "#",
                "report_url": f"{today_date_str}/index.html#art-{idx}",
                "source_name": item.get("source_name") or "Unknown Source",
                "category": item.get("category") or "Security",
                "summary_bn": summary_raw[:220],
                "severity": _normalize_severity(item.get("severity")),
                "score": int(item.get("final_importance_score") or item.get("importance_score") or 50),
                "has_kev": bool(item.get("has_kev_match")),
                "cves": cves,
                "vendors": vendors,
            })

        # Sort index descending by date, then score
        filtered_index.sort(key=lambda x: (x.get("date", ""), x.get("score", 0)), reverse=True)

        json_content = json.dumps(filtered_index, indent=2, ensure_ascii=False)
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(json_content)
        with open(os.path.join(assets_dir, "search_index.json"), "w", encoding="utf-8") as f:
            f.write(json_content)

        js_content = f"window.__THREAT_SEARCH_INDEX__ = {json_content};\n"
        with open(os.path.join(assets_dir, "search_index.js"), "w", encoding="utf-8") as f:
            f.write(js_content)

    def _extract_articles_from_html(self, html_path: str, date_str: str) -> List[Dict[str, Any]]:
        """Fallback backfill helper to extract articles from legacy or existing HTML files."""
        records = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(open(html_path, encoding="utf-8"), "html.parser")
            cards = soup.find_all("article", class_="article-card")
            if not cards:
                cards = soup.find_all("div", class_="article-card")

            date_pretty = _format_pretty_date(date_str)
            for idx, c in enumerate(cards, start=1):
                title_a = c.find("a", class_=re.compile(r"article-title"))
                title = title_a.get_text(strip=True) if title_a else "Untitled"
                source_url = title_a["href"] if title_a and title_a.has_attr("href") else "#"

                badge = c.find("span", class_=re.compile(r"badge-(critical|high|medium|low)"))
                sev = "medium"
                score = 50
                if badge:
                    txt = badge.get_text(strip=True)
                    m = re.search(r"(CRITICAL|HIGH|MEDIUM|LOW)\s*\((\d+)/100\)", txt)
                    if m:
                        sev = m.group(1).lower()
                        score = int(m.group(2))

                has_kev = bool(c.find("span", class_="badge-kev"))
                summary_div = c.find("div", class_=re.compile(r"summary-bn"))
                summary = summary_div.get_text(strip=True) if summary_div else ""

                tags = c.find_all(["span", "a"], class_=re.compile(r"(tag|tag-cve|tag-vendor)"))
                cves = []
                vendors = []
                for t in tags:
                    tt = t.get_text(strip=True)
                    if "cve" in t.get("class", []) or "tag-cve" in t.get("class", []):
                        cves.append(tt.replace("External", "").strip().split()[0])
                    elif "Vendor:" in tt:
                        vendors.append(tt.replace("Vendor:", "").strip())

                records.append({
                    "id": f"{date_str}_art-{idx}",
                    "date": date_str,
                    "date_pretty": date_pretty,
                    "title": title,
                    "source_url": source_url,
                    "report_url": f"{date_str}/index.html#art-{idx}",
                    "source_name": "Historical Report",
                    "category": "Security",
                    "summary_bn": summary[:220],
                    "severity": _normalize_severity(sev),
                    "score": score,
                    "has_kev": has_kev,
                    "cves": cves,
                    "vendors": vendors,
                })
        except Exception:
            pass
        return records

    def _generate_archive_homepage(self):
        """Generates the main index.html archive repository landing page grouped by month."""
        reports_dir = self.config.reports_dir
        subdirs = [
            d for d in os.listdir(reports_dir)
            if os.path.isdir(os.path.join(reports_dir, d)) and d != "assets"
        ]
        subdirs.sort(reverse=True)

        from collections import defaultdict
        month_groups = defaultdict(list)
        for date_str in subdirs:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                month_key = (dt.year, dt.month)
                month_title = dt.strftime("%B %Y")
            except ValueError:
                month_key = (9999, 99)
                month_title = "Other Briefings"
            month_groups[(month_key, month_title)].append(date_str)

        month_sections_html = []
        for (month_key, month_title), dates in month_groups.items():
            links_html = []
            for date_str in dates:
                safe_date = html.escape(date_str)
                safe_pretty_date = html.escape(_format_pretty_date(date_str))
                links_html.append(
                    f'<li><a href="{safe_date}/index.html" class="archive-card-link">'
                    f'  <div class="archive-card-left">'
                    f'    <div class="archive-date-icon">{SVG_ICONS["calendar"]}</div>'
                    f'    <div class="archive-date-info">'
                    f'      <span class="archive-pretty-date">{safe_pretty_date}</span>'
                    f'      <span class="archive-iso-date">{safe_date}</span>'
                    f'    </div>'
                    f'  </div>'
                    f'  {SVG_ICONS["arrow_right"]}'
                    f'</a></li>'
                )

            cards_html = "\n                ".join(links_html)
            count_str = f"{len(dates)} {'Briefing' if len(dates) == 1 else 'Briefings'}"
            month_sections_html.append(
                f'<section class="archive-month-section">'
                f'  <div class="archive-month-header">'
                f'    <h2 class="archive-month-title">'
                f'      {SVG_ICONS["calendar"]}'
                f'      <span>{month_title}</span>'
                f'    </h2>'
                f'    <span class="archive-month-badge">{count_str}</span>'
                f'  </div>'
                f'  <ul class="archive-grid">'
                f'    {cards_html}'
                f'  </ul>'
                f'</section>'
            )

        if not month_sections_html:
            archive_month_sections = '<div class="empty-state">No daily briefings generated yet.</div>'
        else:
            archive_month_sections = "\n\n".join(month_sections_html)

        shared_css = self._load_asset_or_template("styles.css")
        interactive_js = self._load_asset_or_template("report.js")
        archive_template = self._load_asset_or_template("archive_template.html")

        archive_html = archive_template
        replacements = {
            "{{SHARED_CSS}}": shared_css,
            "{{INTERACTIVE_JS}}": interactive_js,
            "{{BRIEFING_COUNT}}": str(len(subdirs)),
            "{{ARCHIVE_MONTH_SECTIONS}}": archive_month_sections,
        }
        for placeholder, value in replacements.items():
            archive_html = archive_html.replace(placeholder, value)

        homepage_path = os.path.join(reports_dir, "index.html")
        with open(homepage_path, "w", encoding="utf-8") as f:
            f.write(archive_html)
