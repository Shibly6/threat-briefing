import html
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.config import AppConfig
from src.utils import format_iso_utc

SEVERITY_LEVELS = ("critical", "high", "medium", "low")


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


SHARED_BASE_CSS = """
        :root {
            --bg-primary: #090d16;
            --bg-secondary: #0f1624;
            --bg-card: #0f1624;
            --bg-card-hover: #131c2e;
            --border-color: #1e293b;
            --border-soft: rgba(148, 163, 184, 0.14);
            --border-strong: rgba(148, 163, 184, 0.28);
            --text-primary: #eaf0fa;
            --text-secondary: #98a7be;
            --text-muted: #7b8aa1;
            --accent-blue: #38bdf8;
            --accent-cyan: #22d3ee;
            --severity-critical: #ff4d5e;
            --severity-high: #ff9448;
            --severity-medium: #fbbf24;
            --severity-low: #34d399;
            --kev-color: #f472b6;
            --glow-critical: rgba(255, 77, 94, 0.35);
            --glow-high: rgba(255, 148, 72, 0.32);
            --glow-blue: rgba(56, 189, 248, 0.32);
            --glow-kev: rgba(244, 114, 182, 0.30);
            --ring: rgba(56, 189, 248, 0.55);
            --radius-sm: 10px;
            --radius-md: 15px;
            --radius-lg: 18px;
            --gap-md: 16px;
            --gap-lg: 28px;
            --ease-smooth: cubic-bezier(0.22, 0.68, 0.32, 1);
            --shadow-card: 0 22px 50px -32px rgba(0, 0, 0, 0.95), inset 0 1px 0 rgba(255, 255, 255, 0.04);
            --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: "JetBrains Mono", "SFMono-Regular", Consolas, "Liberation Mono", monospace;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        html { scroll-behavior: smooth; }

        body {
            font-family: var(--font-sans);
            background-color: var(--bg-primary);
            background-image:
                radial-gradient(900px circle at 12% -8%, rgba(56, 189, 248, 0.10), transparent 60%),
                radial-gradient(800px circle at 88% 0%, rgba(255, 77, 94, 0.08), transparent 55%),
                radial-gradient(700px circle at 50% 110%, rgba(34, 211, 238, 0.06), transparent 60%);
            background-attachment: fixed;
            color: var(--text-primary);
            line-height: 1.68;
            padding: 32px 20px 48px;
            -webkit-font-smoothing: antialiased;
            text-rendering: optimizeLegibility;
        }

        .container { max-width: 1180px; margin: 0 auto; }

        ::selection { background: rgba(56, 189, 248, 0.30); color: #f8fbff; }

        a:focus-visible,
        button:focus-visible {
            outline: 2px solid var(--ring);
            outline-offset: 3px;
            border-radius: 6px;
        }

        header {
            position: relative;
            overflow: hidden;
            background: linear-gradient(160deg, rgba(19, 28, 46, 0.92), rgba(9, 13, 22, 0.94));
            border: 1px solid var(--border-soft);
            border-radius: 18px;
            padding: 26px 30px;
            margin-bottom: var(--gap-lg);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 18px;
            box-shadow: 0 24px 60px -32px rgba(0, 0, 0, 0.9), inset 0 1px 0 rgba(255, 255, 255, 0.04);
        }

        header::before {
            content: "";
            position: absolute;
            inset: 0 0 auto 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent-blue), var(--severity-critical), transparent);
            opacity: 0.85;
        }

        .brand-lockup { display: flex; align-items: center; gap: 16px; }

        .brand-mark {
            width: 48px;
            height: 48px;
            flex-shrink: 0;
            border-radius: 13px;
            display: grid;
            place-items: center;
            font-size: 1.4rem;
            background: linear-gradient(150deg, rgba(56, 189, 248, 0.20), rgba(255, 77, 94, 0.16));
            border: 1px solid rgba(56, 189, 248, 0.35);
            box-shadow: 0 0 22px -6px var(--glow-blue);
        }

        .header-title h1 {
            font-size: 1.62rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            line-height: 1.25;
            color: var(--text-primary);
        }

        .header-title h1 .accent { color: var(--accent-blue); }

        .header-sub {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 7px;
            font-size: 0.78rem;
            color: var(--text-secondary);
            font-family: var(--font-mono);
            letter-spacing: 0.04em;
        }

        .section-label {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.74rem;
            font-family: var(--font-mono);
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin: 0 0 var(--gap-md) 2px;
        }

        .section-label::after {
            content: "";
            flex: 1;
            height: 1px;
            background: linear-gradient(90deg, var(--border-color), transparent);
        }

        footer {
            margin-top: 48px;
            padding: 22px 24px;
            border-radius: var(--radius-lg);
            border: 1px solid var(--border-soft);
            background: linear-gradient(170deg, rgba(19, 28, 46, 0.72), rgba(9, 13, 22, 0.9));
            text-align: center;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
        }

        .footer-credit {
            font-size: 0.84rem;
            font-weight: 500;
            color: var(--text-secondary);
        }

        .footer-credit a {
            color: var(--accent-blue);
            font-weight: 600;
            text-decoration: none;
            transition: color 0.18s ease, text-shadow 0.18s ease;
        }

        .footer-credit a:hover {
            color: #7dd3fc;
            text-shadow: 0 0 14px var(--glow-blue);
            text-decoration: underline;
            text-underline-offset: 4px;
        }
"""


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Cybersecurity threat intelligence briefing for {report_date_pretty}.">
    <meta name="author" content="Noor Elahi Ali Shibly">
    <title>{report_date_pretty} Threat Briefing</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
{shared_css}

        .nav-home {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: var(--accent-blue);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.82rem;
            letter-spacing: 0.02em;
            padding: 9px 16px;
            border-radius: 10px;
            border: 1px solid rgba(56, 189, 248, 0.32);
            background: rgba(56, 189, 248, 0.08);
            transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
        }}

        .nav-home:hover {{
            background: rgba(56, 189, 248, 0.16);
            border-color: rgba(56, 189, 248, 0.6);
            box-shadow: 0 0 22px -6px var(--glow-blue);
            transform: translateY(-1px);
        }}

        .spotlight-box {{
            position: relative;
            overflow: hidden;
            background: linear-gradient(155deg, rgba(19, 28, 46, 0.95), rgba(9, 13, 22, 0.97));
            border: 1px solid rgba(56, 189, 248, 0.26);
            border-radius: 18px;
            padding: 22px 24px 24px;
            margin-bottom: var(--gap-lg);
            box-shadow: 0 26px 60px -34px rgba(56, 189, 248, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.04);
        }}

        .spotlight-box::before {{
            content: "";
            position: absolute;
            top: -60%;
            left: -10%;
            width: 320px;
            height: 320px;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.16), transparent 65%);
            pointer-events: none;
        }}

        .spotlight-box h2 {{
            position: relative;
            font-size: 1.05rem;
            font-weight: 600;
            letter-spacing: -0.01em;
            color: var(--text-primary);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .spotlight-box h2 .fire {{
            display: grid;
            place-items: center;
            width: 28px;
            height: 28px;
            border-radius: 9px;
            font-size: 0.9rem;
            background: rgba(255, 148, 72, 0.14);
            border: 1px solid rgba(255, 148, 72, 0.34);
            box-shadow: 0 0 18px -6px var(--glow-high);
        }}

        .spotlight-list {{ position: relative; display: flex; flex-direction: column; gap: 8px; }}

        .spotlight-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
            padding: 11px 14px;
            background: rgba(148, 163, 184, 0.05);
            border: 1px solid transparent;
            border-radius: var(--radius-sm);
            transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s var(--ease-smooth);
        }}

        .spotlight-item:hover {{
            background: rgba(56, 189, 248, 0.07);
            border-color: rgba(56, 189, 248, 0.26);
            box-shadow: 0 0 24px -12px var(--glow-blue);
            transform: translateX(2px);
        }}

        .spotlight-item a {{
            color: var(--text-primary);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.94rem;
            line-height: 1.45;
            transition: color 0.18s ease;
        }}

        .spotlight-item:hover a {{ color: var(--accent-blue); }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: var(--gap-md);
            margin-bottom: var(--gap-lg);
        }}

        .stat-card {{
            position: relative;
            overflow: hidden;
            background: linear-gradient(165deg, rgba(19, 28, 46, 0.94), rgba(11, 16, 26, 0.96));
            border: 1px solid var(--border-soft);
            border-radius: var(--radius-md);
            padding: 20px 20px 18px;
            transition: transform 0.24s var(--ease-smooth), border-color 0.24s ease, box-shadow 0.24s ease;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
        }}

        .stat-card::after {{
            content: "";
            position: absolute;
            inset: auto 0 0 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent-blue), transparent);
            opacity: 0.5;
            transition: opacity 0.24s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-3px);
            border-color: rgba(56, 189, 248, 0.34);
            box-shadow: 0 22px 46px -28px var(--glow-blue), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }}

        .stat-card:hover::after {{ opacity: 1; }}

        .stat-card .stat-head {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 12px;
        }}

        .stat-card .number {{
            font-family: var(--font-mono);
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -0.03em;
            line-height: 1.05;
            color: var(--text-primary);
            font-variant-numeric: tabular-nums;
        }}

        .stat-card .icon {{
            display: grid;
            place-items: center;
            flex-shrink: 0;
            width: 34px;
            height: 34px;
            border-radius: var(--radius-sm);
            font-size: 0.92rem;
            line-height: 1;
            background: rgba(148, 163, 184, 0.08);
            border: 1px solid var(--border-soft);
            transition: transform 0.24s var(--ease-smooth), border-color 0.24s ease;
        }}

        .stat-card:hover .icon {{ transform: scale(1.06); }}

        .stat-card .label {{
            color: var(--text-secondary);
            font-size: 0.71rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            line-height: 1.35;
        }}

        .stat-card.is-critical {{ border-color: rgba(255, 77, 94, 0.24); }}
        .stat-card.is-critical::after {{ background: linear-gradient(90deg, transparent, var(--severity-critical), transparent); opacity: 0.8; }}
        .stat-card.is-critical:hover {{ border-color: rgba(255, 77, 94, 0.5); box-shadow: 0 22px 46px -26px var(--glow-critical), inset 0 1px 0 rgba(255, 255, 255, 0.05); }}
        .stat-card.is-critical .number, .stat-card.is-critical .icon {{ color: var(--severity-critical); }}
        .stat-card.is-critical .icon {{ background: rgba(255, 77, 94, 0.1); border-color: rgba(255, 77, 94, 0.3); }}

        .stat-card.is-high {{ border-color: rgba(255, 148, 72, 0.22); }}
        .stat-card.is-high::after {{ background: linear-gradient(90deg, transparent, var(--severity-high), transparent); opacity: 0.8; }}
        .stat-card.is-high:hover {{ border-color: rgba(255, 148, 72, 0.48); box-shadow: 0 22px 46px -26px var(--glow-high), inset 0 1px 0 rgba(255, 255, 255, 0.05); }}
        .stat-card.is-high .number, .stat-card.is-high .icon {{ color: var(--severity-high); }}
        .stat-card.is-high .icon {{ background: rgba(255, 148, 72, 0.1); border-color: rgba(255, 148, 72, 0.3); }}

        .stat-card.is-kev {{ border-color: rgba(244, 114, 182, 0.22); }}
        .stat-card.is-kev::after {{ background: linear-gradient(90deg, transparent, var(--kev-color), transparent); opacity: 0.8; }}
        .stat-card.is-kev:hover {{ border-color: rgba(244, 114, 182, 0.48); box-shadow: 0 22px 46px -26px var(--glow-kev), inset 0 1px 0 rgba(255, 255, 255, 0.05); }}
        .stat-card.is-kev .number, .stat-card.is-kev .icon {{ color: var(--kev-color); }}
        .stat-card.is-kev .icon {{ background: rgba(244, 114, 182, 0.1); border-color: rgba(244, 114, 182, 0.3); }}

        .stat-card.is-total .icon {{ color: var(--accent-blue); background: rgba(56, 189, 248, 0.1); border-color: rgba(56, 189, 248, 0.3); }}

        .articles-list {{ display: flex; flex-direction: column; gap: 18px; }}

        .article-card {{
            position: relative;
            background: linear-gradient(168deg, rgba(17, 25, 41, 0.95), rgba(11, 16, 26, 0.97));
            border: 1px solid var(--border-soft);
            border-radius: var(--radius-md);
            padding: 22px 24px;
            transition: transform 0.24s var(--ease-smooth), border-color 0.24s ease, box-shadow 0.24s ease, background 0.24s ease;
            box-shadow: var(--shadow-card);
        }}

        .article-card::before {{
            content: "";
            position: absolute;
            left: 0;
            top: 18px;
            bottom: 18px;
            width: 3px;
            border-radius: 0 3px 3px 0;
            background: linear-gradient(180deg, rgba(56, 189, 248, 0.65), rgba(56, 189, 248, 0));
        }}

        .article-card:hover {{
            transform: translateY(-2px);
            background: linear-gradient(168deg, rgba(21, 31, 49, 0.96), rgba(13, 19, 31, 0.98));
            border-color: rgba(56, 189, 248, 0.28);
            box-shadow: 0 26px 56px -34px rgba(56, 189, 248, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }}

        .article-card.sev-critical::before {{ background: linear-gradient(180deg, var(--severity-critical), rgba(255, 77, 94, 0)); }}
        .article-card.sev-critical:hover {{ border-color: rgba(255, 77, 94, 0.4); box-shadow: 0 26px 56px -32px var(--glow-critical), inset 0 1px 0 rgba(255, 255, 255, 0.05); }}

        .article-card.sev-high::before {{ background: linear-gradient(180deg, var(--severity-high), rgba(255, 148, 72, 0)); }}
        .article-card.sev-high:hover {{ border-color: rgba(255, 148, 72, 0.38); box-shadow: 0 26px 56px -32px var(--glow-high), inset 0 1px 0 rgba(255, 255, 255, 0.05); }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 16px;
            margin-bottom: 12px;
        }}

        .article-title {{
            font-size: 1.07rem;
            font-weight: 600;
            line-height: 1.44;
            letter-spacing: -0.01em;
            text-decoration: none;
            color: var(--text-primary);
            transition: color 0.18s ease;
        }}

        .article-title:hover {{ color: var(--accent-blue); }}

        .badge-group {{ display: flex; align-items: center; gap: 7px; flex-wrap: wrap; justify-content: flex-end; flex-shrink: 0; }}

        .badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 11px;
            border-radius: 8px;
            font-family: var(--font-mono);
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            white-space: nowrap;
            border: 1px solid transparent;
        }}

        .badge-critical {{
            color: #ffd7db;
            background: linear-gradient(150deg, rgba(255, 77, 94, 0.24), rgba(255, 77, 94, 0.10));
            border-color: rgba(255, 77, 94, 0.65);
            box-shadow: 0 0 20px -6px var(--glow-critical), inset 0 0 14px -8px rgba(255, 77, 94, 0.9);
            text-shadow: 0 0 12px rgba(255, 77, 94, 0.55);
            animation: glow-critical 3s ease-in-out infinite;
        }}

        .badge-high {{
            color: #ffe1c7;
            background: linear-gradient(150deg, rgba(255, 148, 72, 0.22), rgba(255, 148, 72, 0.09));
            border-color: rgba(255, 148, 72, 0.60);
            box-shadow: 0 0 20px -6px var(--glow-high), inset 0 0 14px -8px rgba(255, 148, 72, 0.85);
            text-shadow: 0 0 12px rgba(255, 148, 72, 0.5);
            animation: glow-high 3.4s ease-in-out infinite;
        }}

        .badge-medium {{
            color: #fde9a9;
            background: linear-gradient(150deg, rgba(251, 191, 36, 0.17), rgba(251, 191, 36, 0.07));
            border-color: rgba(251, 191, 36, 0.45);
            box-shadow: inset 0 0 12px -8px rgba(251, 191, 36, 0.8);
        }}

        .badge-low {{
            color: #c6f7e3;
            background: linear-gradient(150deg, rgba(52, 211, 153, 0.15), rgba(52, 211, 153, 0.06));
            border-color: rgba(52, 211, 153, 0.42);
            box-shadow: inset 0 0 12px -8px rgba(52, 211, 153, 0.8);
        }}

        .badge-kev {{
            color: #ffd9ee;
            background: linear-gradient(150deg, rgba(244, 114, 182, 0.20), rgba(244, 114, 182, 0.08));
            border-color: rgba(244, 114, 182, 0.52);
            box-shadow: 0 0 18px -8px rgba(244, 114, 182, 0.75);
        }}

        .badge-critical .badge-dot,
        .badge-high .badge-dot {{
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: currentColor;
            box-shadow: 0 0 8px currentColor, 0 0 16px currentColor;
            flex-shrink: 0;
            animation: pulse-dot 1.8s ease-in-out infinite;
        }}

        .article-card:hover .badge-critical,
        .article-card:hover .badge-high,
        .spotlight-item:hover .badge-critical,
        .spotlight-item:hover .badge-high {{
            filter: brightness(1.15) saturate(1.08);
        }}

        @keyframes glow-critical {{
            0%, 100% {{ box-shadow: 0 0 20px -6px var(--glow-critical), inset 0 0 14px -8px rgba(255, 77, 94, 0.9); }}
            50% {{ box-shadow: 0 0 30px -3px var(--glow-critical), inset 0 0 18px -6px rgba(255, 77, 94, 0.95); }}
        }}

        @keyframes glow-high {{
            0%, 100% {{ box-shadow: 0 0 20px -6px var(--glow-high), inset 0 0 14px -8px rgba(255, 148, 72, 0.85); }}
            50% {{ box-shadow: 0 0 28px -4px var(--glow-high), inset 0 0 18px -6px rgba(255, 148, 72, 0.92); }}
        }}

        @keyframes pulse-dot {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.35; }}
        }}

        .meta-bar {{
            display: flex;
            gap: 8px;
            font-size: 0.78rem;
            color: var(--text-secondary);
            margin-bottom: 14px;
            flex-wrap: wrap;
        }}

        .meta-item {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 3px 10px;
            border-radius: 7px;
            border: 1px solid var(--border-soft);
            background: rgba(148, 163, 184, 0.06);
            line-height: 1.5;
            transition: border-color 0.2s ease, background 0.2s ease;
        }}

        .meta-item:hover {{ border-color: var(--border-strong); background: rgba(148, 163, 184, 0.09); }}

        .meta-item strong {{ color: #dbe7f6; font-weight: 600; }}

        .meta-item .e {{ opacity: 0.78; font-size: 0.82rem; }}

        .summary-bn {{
            color: #ccd9ea;
            font-size: 0.95rem;
            line-height: 1.75;
            margin-bottom: 16px;
            direction: ltr;
            text-align: left;
            border-left: 2px solid rgba(56, 189, 248, 0.22);
            padding-left: 14px;
            transition: border-color 0.22s ease;
        }}

        .article-card:hover .summary-bn {{ border-left-color: rgba(56, 189, 248, 0.55); }}

        .tags-container {{ display: flex; gap: 7px; flex-wrap: wrap; align-items: center; }}

        .tag {{
            display: inline-flex;
            align-items: center;
            background: rgba(56, 189, 248, 0.07);
            border: 1px solid rgba(56, 189, 248, 0.20);
            padding: 3px 9px;
            border-radius: 6px;
            font-family: var(--font-mono);
            font-size: 0.72rem;
            letter-spacing: 0.02em;
            color: #9ed8f5;
            transition: background 0.18s ease, border-color 0.18s ease;
        }}

        .tag:hover {{ background: rgba(56, 189, 248, 0.14); border-color: rgba(56, 189, 248, 0.4); }}

        .cve-tag {{
            background: rgba(255, 77, 94, 0.09);
            color: #ffb3bb;
            border-color: rgba(255, 77, 94, 0.30);
        }}

        .cve-tag:hover {{ background: rgba(255, 77, 94, 0.16); border-color: rgba(255, 77, 94, 0.5); }}

        .empty-state {{
            text-align: center;
            padding: 48px 24px;
            border: 1px dashed var(--border-color);
            border-radius: var(--radius-md);
            color: var(--text-muted);
            font-size: 0.92rem;
            background: rgba(148, 163, 184, 0.03);
        }}

        @media (max-width: 720px) {{
            body {{ padding: 18px 13px 32px; }}
            header {{ padding: 22px; margin-bottom: 22px; }}
            .header-title h1 {{ font-size: 1.3rem; }}
            .card-header {{ flex-direction: column; align-items: flex-start; gap: 10px; }}
            .badge-group {{ justify-content: flex-start; }}
            .stat-card .number {{ font-size: 1.7rem; }}
            .spotlight-item {{ flex-direction: column; align-items: flex-start; gap: 8px; }}
            .article-card {{ padding: 18px; }}
            .summary-bn {{ padding-left: 12px; }}
        }}

        @media (prefers-reduced-motion: reduce) {{
            * {{ animation: none !important; transition: none !important; }}
            .stat-card:hover, .article-card:hover, .spotlight-item:hover {{ transform: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand-lockup">
                <div class="brand-mark">🛡️</div>
                <div class="header-title">
                    <h1>{report_date_pretty} <span class="accent">Threat Briefing</span></h1>
                    <div class="header-sub">
                        <span>REPORT DATE // <strong>{report_date_str}</strong></span>
                    </div>
                </div>
            </div>
            <div>
                <a href="../index.html" class="nav-home">← Archive Index</a>
            </div>
        </header>

        <div class="section-label">Threat Telemetry</div>
        <div class="stats-grid">
            <div class="stat-card is-total">
                <div class="stat-head">
                    <div class="number">{total_count}</div>
                    <div class="icon">📰</div>
                </div>
                <div class="label">Total Articles</div>
            </div>
            <div class="stat-card is-critical">
                <div class="stat-head">
                    <div class="number">{critical_count}</div>
                    <div class="icon">🚨</div>
                </div>
                <div class="label">Critical Threats</div>
            </div>
            <div class="stat-card is-high">
                <div class="stat-head">
                    <div class="number">{high_count}</div>
                    <div class="icon">⚠️</div>
                </div>
                <div class="label">High Alerts</div>
            </div>
            <div class="stat-card is-kev">
                <div class="stat-head">
                    <div class="number">{kev_match_count}</div>
                    <div class="icon">🔥</div>
                </div>
                <div class="label">CISA KEV Exploited</div>
            </div>
        </div>

        <div class="spotlight-box">
            <h2><span class="fire">🔥</span> Top 5 Important News Today</h2>
            <div class="spotlight-list">
                {spotlight_html}
            </div>
        </div>

        <div class="section-label">Full Intelligence Feed</div>
        <div class="articles-list">
            {articles_cards_html}
        </div>

        <footer>
            <div class="footer-credit">
                Created by <a href="https://noorelahialishibly.com" target="_blank" rel="noopener noreferrer">Noor Elahi Ali Shibly</a>
            </div>
        </footer>
    </div>
</body>
</html>
"""


ARCHIVE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Daily Briefing Repository of Cybersecurity Threat Intelligence Briefings.">
    <meta name="author" content="Noor Elahi Ali Shibly">
    <title>Threat Briefing Archive</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
{shared_css}

        .archive-count-pill {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 15px;
            border-radius: 10px;
            border: 1px solid rgba(56, 189, 248, 0.28);
            background: rgba(56, 189, 248, 0.08);
            color: var(--accent-blue);
            font-family: var(--font-mono);
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.04em;
        }}

        .archive-panel {{
            position: relative;
            overflow: hidden;
            background: linear-gradient(155deg, rgba(19, 28, 46, 0.95), rgba(9, 13, 22, 0.97));
            border: 1px solid rgba(56, 189, 248, 0.22);
            border-radius: var(--radius-lg);
            padding: 22px 24px 24px;
            box-shadow: var(--shadow-card);
        }}

        .archive-panel::before {{
            content: "";
            position: absolute;
            top: -55%;
            left: -8%;
            width: 320px;
            height: 320px;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.14), transparent 65%);
            pointer-events: none;
        }}

        .archive-list {{
            position: relative;
            list-style: none;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
            gap: 14px;
        }}

        .archive-list li a {{
            position: relative;
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 16px 18px;
            border-radius: var(--radius-md);
            border: 1px solid var(--border-soft);
            background: linear-gradient(168deg, rgba(17, 25, 41, 0.92), rgba(11, 16, 26, 0.95));
            color: var(--text-primary);
            text-decoration: none;
            transition: transform 0.22s var(--ease-smooth), background 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
        }}

        .archive-list li a::before {{
            content: "";
            position: absolute;
            left: 0;
            top: 14px;
            bottom: 14px;
            width: 3px;
            border-radius: 0 3px 3px 0;
            background: linear-gradient(180deg, rgba(56, 189, 248, 0.7), rgba(56, 189, 248, 0));
            opacity: 0.65;
            transition: opacity 0.22s ease;
        }}

        .archive-list li a:hover {{
            transform: translateY(-2px);
            background: linear-gradient(168deg, rgba(21, 31, 49, 0.96), rgba(13, 19, 31, 0.98));
            border-color: rgba(56, 189, 248, 0.38);
            box-shadow: 0 22px 44px -26px var(--glow-blue), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }}

        .archive-list li a:hover::before {{ opacity: 1; }}

        .arc-icon {{
            display: grid;
            place-items: center;
            width: 42px;
            height: 42px;
            flex-shrink: 0;
            border-radius: 11px;
            font-size: 1.05rem;
            background: rgba(56, 189, 248, 0.12);
            border: 1px solid rgba(56, 189, 248, 0.32);
            box-shadow: 0 0 18px -8px var(--glow-blue);
            transition: transform 0.22s var(--ease-smooth);
        }}

        .archive-list li a:hover .arc-icon {{ transform: scale(1.06); }}

        .arc-text {{
            display: flex;
            flex-direction: column;
            gap: 3px;
            min-width: 0;
        }}

        .arc-pretty-date {{
            font-size: 1.08rem;
            font-weight: 700;
            letter-spacing: -0.015em;
            line-height: 1.3;
            color: var(--text-primary);
            transition: color 0.18s ease;
        }}

        .archive-list li a:hover .arc-pretty-date {{ color: var(--accent-blue); }}

        .arc-date {{
            font-family: var(--font-mono);
            font-size: 0.74rem;
            font-weight: 400;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
        }}

        .arc-arrow {{
            margin-left: auto;
            display: grid;
            place-items: center;
            width: 30px;
            height: 30px;
            flex-shrink: 0;
            border-radius: 8px;
            border: 1px solid var(--border-soft);
            background: rgba(148, 163, 184, 0.05);
            color: var(--text-muted);
            font-size: 0.9rem;
            transition: color 0.22s ease, border-color 0.22s ease, background 0.22s ease, transform 0.22s var(--ease-smooth);
        }}

        .archive-list li a:hover .arc-arrow {{
            color: var(--accent-blue);
            border-color: rgba(56, 189, 248, 0.35);
            background: rgba(56, 189, 248, 0.12);
            transform: translateX(3px);
        }}

        .arc-empty {{
            grid-column: 1 / -1;
            padding: 40px 24px;
            text-align: center;
            border: 1px dashed var(--border-color);
            border-radius: var(--radius-md);
            color: var(--text-muted);
            font-size: 0.92rem;
            background: rgba(148, 163, 184, 0.03);
        }}

        @media (max-width: 720px) {{
            body {{ padding: 18px 13px 32px; }}
            header {{ padding: 22px; margin-bottom: 22px; }}
            .header-title h1 {{ font-size: 1.3rem; }}
            .archive-panel {{ padding: 16px; }}
            .archive-list {{ grid-template-columns: 1fr; }}
        }}

        @media (prefers-reduced-motion: reduce) {{
            * {{ animation: none !important; transition: none !important; }}
            .archive-list li a:hover {{ transform: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="brand-lockup">
                <div class="brand-mark">🛡️</div>
                <div class="header-title">
                    <h1>Threat <span class="accent">Briefing Archive</span></h1>
                    <div class="header-sub">
                        <span>DAILY BRIEFING REPOSITORY</span>
                    </div>
                </div>
            </div>
            <div class="archive-count-pill">
                <span>{briefing_count} BRIEFINGS</span>
            </div>
        </header>

        <div class="section-label">Briefing History</div>
        <div class="archive-panel">
            <ul class="archive-list">
                {archive_items_html}
            </ul>
        </div>

        <footer>
            <div class="footer-credit">
                Created by <a href="https://noorelahialishibly.com" target="_blank" rel="noopener noreferrer">Noor Elahi Ali Shibly</a>
            </div>
        </footer>
    </div>
</body>
</html>
"""


class ReportGenerator:
    def __init__(self, config: AppConfig):
        self.config = config

    def generate_html_report(self, analyzed_articles_path: str, output_path: str = None) -> str:
        """Backward compatible helper method for test suites."""
        return self.generate_daily_and_archive_reports(analyzed_articles_path)

    def generate_daily_and_archive_reports(self, final_articles_path: str) -> str:
        if not os.path.exists(final_articles_path):
            raise FileNotFoundError(f"Final articles file not found: {final_articles_path}")

        with open(final_articles_path, "r", encoding="utf-8") as f:
            articles: List[Dict[str, Any]] = json.load(f)

        now_utc = datetime.now(timezone.utc)
        today_date_str = now_utc.strftime("%Y-%m-%d")
        today_date_pretty = _format_pretty_date(today_date_str)
        _ = format_iso_utc(now_utc)

        date_dir = os.path.join(self.config.reports_dir, today_date_str)
        os.makedirs(date_dir, exist_ok=True)
        date_report_path = os.path.join(date_dir, "index.html")

        # Sort articles by score
        sorted_articles = sorted(
            articles,
            key=lambda x: int(x.get("final_importance_score") or x.get("importance_score") or 0),
            reverse=True,
        )

        spotlight_items = sorted_articles[:5]
        spotlight_html_list = []
        for item in spotlight_items:
            title = html.escape(item.get("title") or "Untitled")
            url = html.escape(item.get("source_url") or "#")
            score = int(item.get("final_importance_score") or item.get("importance_score") or 50)
            sev = _normalize_severity(item.get("severity"))

            dot = '<span class="badge-dot"></span>' if sev in ("critical", "high") else ""
            spotlight_html_list.append(
                f'<div class="spotlight-item">'
                f'<a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
                f'<span class="badge badge-{sev}">{dot}{sev.upper()} ({score}/100)</span>'
                f'</div>'
            )
        spotlight_html = "\n".join(spotlight_html_list) or (
            '<div class="empty-state">No high-priority items surfaced in this cycle.</div>'
        )

        total_count = len(sorted_articles)
        severity_counts = {level: 0 for level in SEVERITY_LEVELS}
        for article in sorted_articles:
            severity_counts[_normalize_severity(article.get("severity"))] += 1
        critical_count = severity_counts["critical"]
        high_count = severity_counts["high"]
        kev_match_count = sum(1 for a in sorted_articles if a.get("has_kev_match", False))

        cards_html_list = []
        for art in sorted_articles:
            sev = _normalize_severity(art.get("severity"))
            title = html.escape(art.get("title") or "Untitled")
            source_url = html.escape(art.get("source_url") or "#")
            source_name = html.escape(art.get("source_name") or "Unknown Source")
            category = html.escape(art.get("category") or "Security")
            summary_bn = html.escape(art.get("summary_bn") or art.get("summary") or "")
            final_score = int(art.get("final_importance_score") or art.get("importance_score") or 50)
            max_cvss = float(art.get("max_cvss_score") or 0.0)
            ai_provider = html.escape(art.get("ai_provider") or "Gemini")

            kev_badge = '<span class="badge badge-kev">🔥 KEV EXPLOITED</span>' if art.get("has_kev_match") else ""
            dot = '<span class="badge-dot"></span>' if sev in ("critical", "high") else ""
            card_sev_class = f" sev-{sev}" if sev in ("critical", "high") else ""

            tags_html = []
            for cve in art.get("cves_mentioned") or []:
                tags_html.append(f'<span class="tag cve-tag">{html.escape(str(cve))}</span>')

            if max_cvss > 0:
                tags_html.append(f'<span class="tag">CVSS: {max_cvss:.1f}</span>')

            for vendor in art.get("affected_vendors") or []:
                tags_html.append(f'<span class="tag">Vendor: {html.escape(str(vendor))}</span>')

            tags_block = (
                f'<div class="tags-container">{" ".join(tags_html)}</div>'
                if tags_html
                else ""
            )

            card = f"""
            <div class="article-card{card_sev_class}">
                <div class="card-header">
                    <a href="{source_url}" target="_blank" rel="noopener noreferrer" class="article-title">{title}</a>
                    <div class="badge-group">
                        <span class="badge badge-{sev}">{dot}{sev.upper()} ({final_score}/100)</span>
                        {kev_badge}
                    </div>
                </div>
                <div class="meta-bar">
                    <span class="meta-item"><span class="e">📰</span><strong>{source_name}</strong></span>
                    <span class="meta-item"><span class="e">🏷️</span>{category}</span>
                    <span class="meta-item"><span class="e">🤖</span>AI: <strong>{ai_provider}</strong></span>
                </div>
                <div class="summary-bn">
                    {summary_bn}
                </div>
                {tags_block}
            </div>
            """
            cards_html_list.append(card)

        articles_cards_html = "\n".join(cards_html_list) or (
            '<div class="empty-state">No threat intelligence articles available in this briefing cycle.</div>'
        )

        final_html = HTML_TEMPLATE.format(
            shared_css=SHARED_BASE_CSS,
            report_date_str=today_date_str,
            report_date_pretty=today_date_pretty,
            total_count=total_count,
            critical_count=critical_count,
            high_count=high_count,
            kev_match_count=kev_match_count,
            spotlight_html=spotlight_html,
            articles_cards_html=articles_cards_html,
        )

        with open(date_report_path, "w", encoding="utf-8") as f:
            f.write(final_html)

        self._generate_archive_homepage()
        return date_report_path

    def _generate_archive_homepage(self):
        reports_dir = self.config.reports_dir
        subdirs = [
            d for d in os.listdir(reports_dir)
            if os.path.isdir(os.path.join(reports_dir, d)) and d != "assets"
        ]
        subdirs.sort(reverse=True)

        links_html = []
        for date_str in subdirs:
            safe_date = html.escape(date_str)
            safe_pretty_date = html.escape(_format_pretty_date(date_str))
            links_html.append(
                f'<li><a href="{safe_date}/index.html">'
                f'<span class="arc-icon">📅</span>'
                f'<span class="arc-text">'
                f'<span class="arc-pretty-date">{safe_pretty_date}</span>'
                f'<span class="arc-date">{safe_date}</span>'
                f'</span>'
                f'<span class="arc-arrow">→</span></a></li>'
            )
        if not links_html:
            links_html.append('<li class="arc-empty">No daily briefings generated yet.</li>')

        archive_items_html = "\n                ".join(links_html)

        archive_html = ARCHIVE_TEMPLATE.format(
            shared_css=SHARED_BASE_CSS,
            briefing_count=len(subdirs),
            archive_items_html=archive_items_html,
        )

        homepage_path = os.path.join(reports_dir, "index.html")
        with open(homepage_path, "w", encoding="utf-8") as f:
            f.write(archive_html)