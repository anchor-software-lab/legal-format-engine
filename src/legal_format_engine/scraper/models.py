"""Pydantic models for court e-filing requirements scraping.

Includes source reliability assessment following CRAAP test methodology
(Currency, Relevance, Authority, Accuracy, Purpose) adapted for legal
data sources.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Source reliability
# ---------------------------------------------------------------------------


class SourceTier(str, Enum):
    """Tiered classification of source authority.

    Based on legal research hierarchy:
    - OFFICIAL: Government/court-operated (.gov, .courts, .uscourts)
    - QUASI_OFFICIAL: Court-contracted vendors (Tyler Technologies/Odyssey,
      File & Serve), bar associations, legal aid orgs
    - SECONDARY: Legal publishers (Westlaw, LexisNexis, Justia), law firms
    - TERTIARY: News, blogs, forums, unverified sources
    """

    OFFICIAL = "official"
    QUASI_OFFICIAL = "quasi_official"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"


class SourceReliability(BaseModel):
    """Reliability assessment for a scraped data source.

    Implements an adapted CRAAP framework for legal data:
    - Currency: How recent is the information?
    - Relevance: Does it address e-filing requirements specifically?
    - Authority: Is the source an official court system?
    - Accuracy: Can requirements be cross-referenced?
    - Purpose: Is it informational (good) vs. promotional (suspect)?

    Each dimension scored 0.0-1.0, combined into an overall score.
    """

    source_url: str
    domain: str  # extracted domain (e.g., "wicourts.gov")
    tier: SourceTier

    # CRAAP dimensions (0.0-1.0 each)
    currency: float = 0.0
    relevance: float = 0.0
    authority: float = 0.0
    accuracy: float = 0.0
    purpose: float = 0.0

    # Cross-reference tracking
    corroborated_by: list[str] = []  # URLs that confirm same requirements
    contradicted_by: list[str] = []  # URLs with conflicting info

    # Metadata
    assessed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    assessor_notes: str = ""

    @property
    def overall_score(self) -> float:
        """Weighted reliability score.

        Authority is weighted 2x because for legal requirements, the
        source's official status is the strongest indicator of reliability.
        """
        weights = {
            "currency": 1.0,
            "relevance": 1.0,
            "authority": 2.0,
            "accuracy": 1.5,
            "purpose": 0.5,
        }
        total_weight = sum(weights.values())
        weighted_sum = (
            self.currency * weights["currency"]
            + self.relevance * weights["relevance"]
            + self.authority * weights["authority"]
            + self.accuracy * weights["accuracy"]
            + self.purpose * weights["purpose"]
        )
        return round(weighted_sum / total_weight, 3)

    @property
    def is_trustworthy(self) -> bool:
        """Whether this source meets minimum reliability threshold.

        Official sources are always trusted. Others need score >= 0.6
        and at least one corroborating source.
        """
        if self.tier == SourceTier.OFFICIAL:
            return True
        if self.overall_score >= 0.6 and len(self.corroborated_by) >= 1:
            return True
        return False

    @property
    def needs_verification(self) -> bool:
        """Whether extracted requirements need manual review."""
        if self.tier == SourceTier.OFFICIAL:
            return False
        if self.tier == SourceTier.QUASI_OFFICIAL and self.overall_score >= 0.7:
            return False
        return True


# ---------------------------------------------------------------------------
# Court system models
# ---------------------------------------------------------------------------


class CourtLevel(str, Enum):
    """Court hierarchy levels."""

    SUPREME = "supreme"
    APPELLATE = "appellate"
    CIRCUIT = "circuit"  # trial-level (state)
    DISTRICT = "district"  # trial-level (federal)
    MUNICIPAL = "municipal"
    SPECIALTY = "specialty"  # bankruptcy, tax, family, etc.


class CourtSystem(BaseModel):
    """A court system or specific court within a jurisdiction."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    name: str  # e.g., "Wisconsin Circuit Court"
    jurisdiction: str  # e.g., "WI", "US-7CIR"
    state: str | None = None  # US state abbreviation
    level: CourtLevel
    parent_system: str | None = None  # e.g., "Wisconsin Court System"

    # E-filing portal info
    efiling_portal_url: str | None = None
    efiling_vendor: str | None = None  # e.g., "Tyler Technologies", "File & Serve"
    efiling_system_name: str | None = None  # e.g., "eFiling", "Odyssey", "CM/ECF"

    # Scraping metadata
    requirements_urls: list[str] = []  # pages with formatting requirements
    last_scraped: str | None = None
    scrape_successful: bool = False


class EFilingRequirement(BaseModel):
    """A specific e-filing formatting requirement extracted from a court source.

    Each requirement is a single rule (e.g., "3-inch top margin for proposed
    orders") with provenance tracking back to its source.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    court_system_id: str  # FK to CourtSystem
    jurisdiction: str

    # The requirement itself
    category: str  # "margin", "font", "file_format", "signature", "general"
    field: str  # e.g., "margin_top_inches", "font_family", "file_format"
    value: str | float | bool | list  # the required value
    condition: str | None = None  # when this applies, e.g., "proposed_order"
    description: str  # human-readable description
    mandatory: bool = True

    # Provenance
    source_url: str
    source_text: str = ""  # the exact text from the page
    reliability: SourceReliability | None = None

    # Metadata
    extracted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    effective_date: str | None = None  # when the requirement took effect
    last_verified: str | None = None

    @property
    def is_verified(self) -> bool:
        """Whether this requirement comes from a trusted source."""
        if self.reliability is None:
            return False
        return self.reliability.is_trustworthy


class ScrapedPage(BaseModel):
    """Record of a scraped web page with metadata for auditing."""

    url: str
    domain: str
    fetched_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    http_status: int = 0
    content_hash: str = ""  # SHA-256 of page content for change detection
    title: str = ""
    last_modified: str | None = None  # from HTTP headers or page content
    robots_txt_allowed: bool = True
    response_time_ms: float = 0.0

    # Extracted data counts
    requirements_found: int = 0
    links_found: int = 0


# ---------------------------------------------------------------------------
# Jurisdiction profile (aggregate)
# ---------------------------------------------------------------------------


class JurisdictionProfile(BaseModel):
    """Aggregated e-filing requirements for a jurisdiction.

    This is the output consumed by both the ML engine (for training data)
    and the legal format engine (for rule generation).
    """

    jurisdiction: str  # e.g., "WI", "US-FED"
    jurisdiction_name: str  # e.g., "Wisconsin"
    courts: list[CourtSystem] = []
    requirements: list[EFilingRequirement] = []

    # Reliability summary
    official_source_count: int = 0
    verified_requirement_count: int = 0
    unverified_requirement_count: int = 0

    # Metadata
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def add_requirement(self, req: EFilingRequirement) -> None:
        """Add a requirement and update reliability counts."""
        self.requirements.append(req)
        if req.is_verified:
            self.verified_requirement_count += 1
        else:
            self.unverified_requirement_count += 1
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def requirements_by_category(self, category: str) -> list[EFilingRequirement]:
        """Filter requirements by category."""
        return [r for r in self.requirements if r.category == category]

    def to_ruleset_dict(self) -> dict:
        """Convert verified requirements to a dict compatible with
        anchor-ml-engine's rule hierarchy format."""
        ruleset: dict = {
            "jurisdiction": self.jurisdiction,
            "jurisdiction_name": self.jurisdiction_name,
            "rules": {},
        }
        for req in self.requirements:
            if not req.is_verified:
                continue
            key = req.field
            if req.condition:
                key = f"{req.condition}.{req.field}"
            ruleset["rules"][key] = {
                "value": req.value,
                "mandatory": req.mandatory,
                "source_url": req.source_url,
                "description": req.description,
            }
        return ruleset
