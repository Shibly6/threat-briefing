from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

@dataclass
class DeduplicationReport:
    total_before: int = 0
    removed_by_age: int = 0
    removed_by_url: int = 0
    removed_by_guid: int = 0
    removed_by_title: int = 0
    removed_by_content: int = 0
    final_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class FeedSource:
    name: str
    xml_url: str
    category: str = "Uncategorized"

@dataclass
class ArticleMetadata:
    source_name: str
    title: str
    url: str
    guid: str
    published_at_utc: Optional[str]
    fetched_at_utc: str
    category: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class FeedValidationResult:
    feed_name: str
    xml_url: str
    status: str
    http_status: Optional[int]
    articles_found: int
    last_published_utc: Optional[str]
    checked_at_utc: str
    is_stale: bool
    error_message: str
    articles: List[ArticleMetadata] = field(default_factory=list)

    def to_status_dict(self) -> Dict[str, Any]:
        return {
            "feed_name": self.feed_name,
            "xml_url": self.xml_url,
            "status": self.status,
            "http_status": self.http_status,
            "articles_found": self.articles_found,
            "last_published_utc": self.last_published_utc,
            "checked_at_utc": self.checked_at_utc,
            "is_stale": self.is_stale,
            "error_message": self.error_message
        }

@dataclass
class ExtractedArticle:
    source_url: str
    canonical_url: Optional[str]
    guid: str
    source_name: str
    title: str
    author: Optional[str]
    published_at_utc: Optional[str]
    content_text: str
    character_count: int
    word_count: int
    extraction_status: str  # "success", "partial", "failed"
    quality_warnings: List[str] = field(default_factory=list)
    error_message: str = "None"
    extracted_at_utc: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class AnalyzedArticle:
    source_url: str
    canonical_url: Optional[str]
    guid: str
    source_name: str
    title: str
    published_at_utc: Optional[str]
    summary: str
    category: str
    severity: str  # "low", "medium", "high", "critical"
    affected_vendors: List[str]
    affected_products: List[str]
    cves_mentioned: List[str]
    attack_type: str
    importance_score: int  # 0 to 100
    analyzed_at_utc: str
    ai_provider: str = "Gemini"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class NvdCveData:
    cve_id: str
    cvss_score: float = 0.0
    cvss_severity: str = "UNKNOWN"
    vendor: str = "Unknown"
    product: str = "Unknown"
    nvd_description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class KevCveData:
    cve_id: str
    is_kev: bool = False
    date_added: str = ""
    due_date: str = ""
    ransomware_associated: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class EnrichedArticle:
    source_url: str
    canonical_url: Optional[str]
    guid: str
    source_name: str
    title: str
    published_at_utc: Optional[str]
    summary_bn: str
    category: str
    severity: str
    affected_vendors: List[str]
    affected_products: List[str]
    cves_mentioned: List[str]
    attack_type: str
    base_importance_score: int
    final_importance_score: int
    nvd_data: List[Dict[str, Any]]
    kev_data: List[Dict[str, Any]]
    has_kev_match: bool
    max_cvss_score: float
    analyzed_at_utc: str
    ai_provider: str = "Gemini"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RunHistoryRecord:
    execution_date: str
    duration_seconds: float
    raw_articles_count: int
    deduplicated_count: int
    analyzed_count: int
    cves_found_count: int
    kev_matches_count: int
    status: str
    error_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)