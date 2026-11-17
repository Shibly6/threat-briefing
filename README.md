# Threat Briefing

**An AI-powered cybersecurity threat intelligence dashboard that collects security news, generates Bengali technical summaries, enriches vulnerability data, and ranks emerging threats by importance.**

[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-brightgreen?logo=github)](https://threatbriefing.noorelahialishibly.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)

**Live Dashboard:** https://threatbriefing.noorelahialishibly.com/

**Developed by [Noor Elahi Ali Shibly](https://noorelahialishibly.com/)** — Software Engineering graduate with a major in Cybersecurity, interested in threat intelligence, vulnerability assessment, and security research.

---

## Overview

Threat Briefing is an automated cybersecurity news monitoring and intelligence platform. It collects articles from security news sources, analyzes them using AI, enriches vulnerability information, and publishes a daily briefing dashboard.

## Features

- **Bengali AI Summaries:** Technical summaries generated using multiple AI providers.
- **Threat Scoring:** 0–100 importance score with severity levels.
- **Vulnerability Intelligence:** CVE identification, CVSS enrichment, and CISA KEV matching.
- **Threat Classification:** Category, affected vendors, products, and attack types.
- **Daily Dashboard:** Telemetry, Top 5 threats, and categorized news.
- **Historical Archive:** Browse previous briefings by date.

## How It Works

The system follows an automated intelligence pipeline:

1. **Collection:** Fetches cybersecurity articles from RSS/Atom feeds.
2. **Extraction:** Extracts article content and removes duplicates.
3. **AI Analysis:** Generates Bengali summaries and identifies security-related information.
4. **Enrichment:** Retrieves CVSS information from NVD and exploitation status from CISA KEV.
5. **Ranking:** Calculates threat importance scores.
6. **Publishing:** Generates static HTML reports and deploys them to GitHub Pages.

### AI Provider Fallback

The system uses a three-provider fallback mechanism:

| Priority | Provider |
|---|---|
| Primary | Google Gemini |
| Fallback 1 | Groq |
| Fallback 2 | OpenRouter |

If a provider encounters rate limits or service errors, the system attempts the next available provider.

### Threat Scoring

Articles receive an AI-generated base importance score (default: 50), which is adjusted using additional factors:

| Factor | Adjustment |
|---|---:|
| Critical severity | × 1.25 |
| High severity | × 1.10 |
| Medium severity | × 1.00 |
| Low severity | × 0.80 |
| CVSS ≥ 9.0 | +15 |
| CVSS ≥ 7.0 | +10 |
| CVSS ≥ 4.0 | +5 |
| CISA KEV match | +25 |
| Published within 12 hours | +10 |
| Published within 24 hours | +5 |

The final score is capped between 0 and 100. Articles are ranked by importance score, followed by CVSS score.

*Note: This is a heuristic ranking system, not an official vulnerability severity assessment.*

## Project Structure

```text
threat-briefing/
├── .github/
│   └── workflows/     # Automation and deployment
├── config/            # Application settings
├── feeds/             # RSS/Atom feed configuration
├── src/               # Core application modules
├── reports/           # Generated HTML briefings
├── requirements.txt
├── LICENSE
└── README.md
```

## Setup

### Requirements

- Python 3.10+
- Git
- API keys for at least one supported AI provider

### 1. Clone the Repository

```bash
git clone https://github.com/Shibly6/threat-briefing.git
cd threat-briefing
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

Add the following secrets to your GitHub repository under:

`Settings → Secrets and variables → Actions`

| Secret | Requirement |
|---|---|
| `GEMINI_API_KEY` | Primary AI provider |
| `GROQ_API_KEY` | Fallback provider |
| `OPENROUTER_API_KEY` | Secondary fallback |
| `NVD_API_KEY` | Optional; improved NVD API access |

At least one AI provider key is required. Configure the remaining providers to enable fallback functionality.

### 4. Enable GitHub Pages

Navigate to:

`Settings → Pages → Build and deployment`

Set the Source to **GitHub Actions**.

### 5. Run Locally

Run a limited test:

```bash
python -m src.cli_daily --test-mode
```

Run the regular pipeline:

```bash
python -m src.cli_daily
```

## Automated Workflow

The project uses GitHub Actions to execute the briefing pipeline and publish the generated reports.

- **Execution time:** Daily at 07:30 AM (Asia/Dhaka).
- **Trigger:** External cron-job.org service using GitHub's `workflow_dispatch` event.
- **Deployment:** GitHub Pages.

**Why an external scheduler?**

GitHub's native scheduled workflow trigger did not reliably execute in this repository during testing. Therefore, an external cron-job.org trigger was configured to initiate the workflow through `workflow_dispatch`.

This approach provides an alternative scheduling mechanism for consistent daily execution.

## Intelligence Sources

The platform collects cybersecurity news and vulnerability information from sources including:

- [The Hacker News](https://thehackernews.com/)
- [SecurityWeek](https://www.securityweek.com/)
- [BleepingComputer](https://www.bleepingcomputer.com/)
- [Unit 42](https://unit42.paloaltonetworks.com/)
- [Microsoft Security Blog](https://www.microsoft.com/en-us/security/blog/)
- [Google / Mandiant](https://cloud.google.com/blog/topics/threat-intelligence)
- [CISA Known Exploited Vulnerabilities](https://www.cisa.gov/known-exploited-vulnerabilities-catalog)
- [National Vulnerability Database](https://nvd.nist.gov/)

Original article links are provided on individual briefing cards so readers can verify the information from its source.

## Known Limitations

- AI-generated summaries and extracted metadata may contain inaccuracies.
- Vendor and product identification is not always precise.
- Threat scores are heuristic and may cluster around the maximum score.
- Article availability and extraction quality depend on external websites.
- AI provider availability and API rate limits can affect processing.

## Disclaimer

Threat Briefing is an independent cybersecurity news aggregation and research project.

- AI-generated summaries may contain factual or technical errors.
- Threat scores are heuristic indicators, not official CVSS ratings or security advisories.
- Vendor and product attribution should be independently verified.
- Always consult original articles, official vendor advisories, NVD, and CISA before making security decisions.

This project is intended for educational, informational, and cybersecurity research purposes.

## License

This project is licensed under the [MIT License](LICENSE).

## Author

**Noor Elahi Ali Shibly**

Software Engineering Graduate | Cybersecurity

- **Portfolio:** https://noorelahialishibly.com/
- **GitHub:** https://github.com/Shibly6
- **LinkedIn:** https://linkedin.com/in/shibly6

Interested in cybersecurity, threat intelligence, vulnerability research, and building practical security tools.

---

*Built to make cybersecurity intelligence more accessible through automation and Bengali AI-powered analysis.*