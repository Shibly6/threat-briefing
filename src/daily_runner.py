import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any

from src.config import AppConfig
from src.logger import setup_logger
from src.collector import FeedCollector
from src.article_extractor import ArticleExtractor
from src.deduplicator import ArticleDeduplicator
from src.gemini_engine import GeminiEngine
from src.nvd_enricher import NvdEnricher
from src.kev_enricher import KevEnricher
from src.ranking_engine import RankingEngine
from src.report_generator import ReportGenerator
from src.models import ArticleMetadata, RunHistoryRecord

class DailyPipelineRunner:
    def __init__(self, config: AppConfig, dry_run: bool = False, verbose: bool = False, test_mode: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.verbose = verbose
        self.test_mode = test_mode or config.test_mode
        self.logger = setup_logger(config, verbose)

    def run(self, opml_path: str = "feeds/cyber_security_feeds.opml") -> Dict[str, Any]:
        start_time = time.time()
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        self.logger.info("==================================================================")
        self.logger.info(f"    STARTING CYBER THREAT INTELLIGENCE PIPELINE [{today_str}]    ")
        self.logger.info("==================================================================")

        cves_found_set = set()
        kev_matches_count = 0
        status = "SUCCESS"
        error_summary = "None"

        try:
            # 1. Feed Collection
            self.logger.info("[Step 1/7] Collecting Live RSS/Atom Feeds...")
            collector = FeedCollector(self.config)
            feed_results = collector.run(opml_path)
            
            with open(self.config.raw_articles_file, "r", encoding="utf-8") as f:
                raw_articles = json.load(f)
            self.logger.info(f"   ↳ Collected {len(raw_articles)} raw articles across {len(feed_results)} feeds.")

            # 2. Extraction
            self.logger.info("[Step 2/7] Extracting Article Contents...")
            extractor = ArticleExtractor(self.config)
            
            process_raw = raw_articles
            if self.test_mode:
                limit = self.config.test_mode_article_limit
                self.logger.info(f"   [TEST MODE ACTIVE] Limiting extraction to {limit} articles.")
                process_raw = raw_articles[:limit]

            extracted_list = []
            for item in process_raw:
                meta = ArticleMetadata(
                    source_name=item.get("source_name", "Unknown"),
                    title=item.get("title", "Untitled"),
                    url=item["url"],
                    guid=item.get("guid", item["url"]),
                    published_at_utc=item.get("published_at_utc"),
                    fetched_at_utc=item.get("fetched_at_utc", "")
                )
                res = extractor.extract_article(meta)
                extracted_list.append(res)

            with open(self.config.article_content_file, "w", encoding="utf-8") as f:
                json.dump([e.to_dict() for e in extracted_list], f, indent=2, ensure_ascii=False)

            # 3. Deduplication
            self.logger.info("[Step 3/7] Deduplicating & Freshness Filtering...")
            deduplicator = ArticleDeduplicator(self.config)
            deduped_articles, dedup_report = deduplicator.run_pipeline(
                input_file=self.config.article_content_file,
                output_file=self.config.deduplicated_articles_file
            )
            self.logger.info(f"   ↳ Retained {len(deduped_articles)} fresh deduplicated articles.")

            # 4. AI Intelligence Analysis
            self.logger.info("[Step 4/7] Running AI Intelligence Analysis (Bangla Summaries)...")
            gemini_engine = GeminiEngine(self.config)
            
            valid_deduped = [
                art for art in deduped_articles
                if art.get("extraction_status") in ("success", "partial") and len(art.get("content_text", "")) >= 20
            ]

            process_deduped = valid_deduped
            if not self.test_mode and len(valid_deduped) > self.config.max_daily_analysis_limit:
                limit = self.config.max_daily_analysis_limit
                self.logger.info(f"   ↳ Capping daily AI analysis to top {limit} valid articles.")
                process_deduped = valid_deduped[:limit]

            analyzed_list = []
            for art in process_deduped:
                res = gemini_engine.analyze_article(art, is_dry_run=self.dry_run)
                if res:
                    analyzed_list.append(res.to_dict())

            with open(self.config.analyzed_articles_file, "w", encoding="utf-8") as f:
                json.dump(analyzed_list, f, indent=2, ensure_ascii=False)

            stats_parts = [f"{provider}: {count}" for provider, count in gemini_engine.stats.items() if count > 0]
            stats_str = f" ({', '.join(stats_parts)})" if stats_parts else ""
            self.logger.info(f"   ↳ AI Engine successfully analyzed {len(analyzed_list)} articles{stats_str}.")

            # 5. NVD & CISA KEV Enrichment
            self.logger.info("[Step 5/7] Enriching with NVD CVSS & CISA KEV Catalog...")
            nvd_enricher = NvdEnricher(self.config)
            kev_enricher = KevEnricher(self.config)

            enriched_list = []
            for art in analyzed_list:
                cves = art.get("cves_mentioned", [])
                nvd_data_list = []
                kev_data_list = []
                max_cvss = 0.0
                has_kev = False

                for cve in cves:
                    cves_found_set.add(cve)
                    nvd_res = nvd_enricher.fetch_cve_details(cve)
                    nvd_data_list.append(nvd_res.to_dict())
                    if nvd_res.cvss_score > max_cvss:
                        max_cvss = nvd_res.cvss_score

                    kev_res = kev_enricher.check_cve(cve)
                    kev_data_list.append(kev_res.to_dict())
                    if kev_res.is_kev:
                        has_kev = True
                        kev_matches_count += 1

                art["summary_bn"] = art.get("summary", "")
                art["nvd_data"] = nvd_data_list
                art["kev_data"] = kev_data_list
                art["has_kev_match"] = has_kev
                art["max_cvss_score"] = max_cvss
                enriched_list.append(art)

            with open(self.config.enriched_articles_file, "w", encoding="utf-8") as f:
                json.dump(enriched_list, f, indent=2, ensure_ascii=False)

            # 6. Improved Deterministic Ranking
            self.logger.info("[Step 6/7] Calculating Deterministic Ranking Scores...")
            ranking_engine = RankingEngine(self.config)
            ranked_list = ranking_engine.rank_articles(enriched_list)

            with open(self.config.final_articles_file, "w", encoding="utf-8") as f:
                json.dump(ranked_list, f, indent=2, ensure_ascii=False)

            # 7. HTML Report Generation
            self.logger.info("[Step 7/7] Generating Dated HTML Briefing & Archive Homepage...")
            report_gen = ReportGenerator(self.config)
            date_report_path = report_gen.generate_daily_and_archive_reports(self.config.final_articles_file)
            self.logger.info(f"   ↳ Report generated at: {date_report_path}")

        except Exception as e:
            status = "FAILED"
            error_summary = str(e)
            self.logger.error(f"Pipeline Execution Error: {e}", exc_info=True)

        duration = round(time.time() - start_time, 2)
        
        history_record = RunHistoryRecord(
            execution_date=today_str,
            duration_seconds=duration,
            raw_articles_count=len(raw_articles) if 'raw_articles' in locals() else 0,
            deduplicated_count=len(deduped_articles) if 'deduped_articles' in locals() else 0,
            analyzed_count=len(analyzed_list) if 'analyzed_list' in locals() else 0,
            cves_found_count=len(cves_found_set),
            kev_matches_count=kev_matches_count,
            status=status,
            error_summary=error_summary
        )

        self._save_run_history(history_record)

        self.logger.info("==================================================================")
        self.logger.info(f" PIPELINE COMPLETED IN {duration}s | STATUS: {status}")
        self.logger.info("==================================================================\n")

        return history_record.to_dict()

    def _save_run_history(self, record: RunHistoryRecord):
        history = []
        if os.path.exists(self.config.run_history_file):
            try:
                with open(self.config.run_history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []

        history.append(record.to_dict())
        os.makedirs(os.path.dirname(self.config.run_history_file), exist_ok=True)
        with open(self.config.run_history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)