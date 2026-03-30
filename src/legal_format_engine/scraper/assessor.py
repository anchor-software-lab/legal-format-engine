"""Source reliability assessor for court e-filing data.

Implements the full CRAAP assessment (Currency, Relevance, Authority,
Accuracy, Purpose) with legal-domain-specific heuristics.

Best practices implemented:
1. Triangulation: cross-reference requirements across multiple sources
2. Source hierarchy: official > quasi-official > secondary > tertiary
3. Temporal validation: flag stale data (>2 years without update)
4. Content analysis: check for specificity (exact values vs. vague guidance)
5. Provenance tracking: every requirement traces back to source text
"""

from __future__ import annotations

import re
import logging
from datetime import datetime, timezone

from legal_format_engine.scraper.models import (
    EFilingRequirement,
    SourceReliability,
    SourceTier,
)

logger = logging.getLogger(__name__)

# Maximum age (in days) before a source is considered potentially stale
_STALE_THRESHOLD_DAYS = 730  # 2 years

# Patterns indicating specific, actionable requirements
_SPECIFICITY_PATTERNS = [
    r"\d+[\-\s]?inch",  # "3-inch margin", "1 inch"
    r"\d+\s*pt",  # "12pt font"
    r"\.\w{3,4}\b",  # file extensions: ".docx", ".pdf"
    r"(?:must|shall|required|mandatory)",  # mandatory language
    r"(?:margin|font|spacing|format)",  # formatting terms
    r"\d+\s*(?:dxa|twip|point|pixel)",  # measurement units
]

# Patterns indicating vague, non-actionable content
_VAGUE_PATTERNS = [
    r"(?:may|might|could|should consider)",
    r"(?:generally|typically|usually|often)",
    r"(?:contact .* for (?:more|additional) (?:information|details))",
]


class ReliabilityAssessor:
    """Assesses and tracks reliability of scraped court data sources.

    Usage::

        assessor = ReliabilityAssessor()
        reliability = assessor.assess_page(url, page_text, page_date)
        assessor.cross_reference(requirement, other_sources)
    """

    def __init__(self) -> None:
        self._known_requirements: dict[str, list[EFilingRequirement]] = {}
        self._source_assessments: dict[str, SourceReliability] = {}

    def assess_page(
        self,
        reliability: SourceReliability,
        page_text: str,
        page_date: str | None = None,
    ) -> SourceReliability:
        """Refine a SourceReliability assessment based on page content.

        Args:
            reliability: Initial assessment (from BaseScraper.assess_source)
            page_text: Extracted text content of the page
            page_date: ISO date string of page's last update, if available
        """
        # 1. Currency assessment
        reliability.currency = self._assess_currency(page_date)

        # 2. Relevance assessment
        reliability.relevance = self._assess_relevance(page_text)

        # 3. Accuracy assessment (specificity of content)
        reliability.accuracy = self._assess_accuracy(page_text)

        # Cache this assessment
        self._source_assessments[reliability.source_url] = reliability
        return reliability

    def _assess_currency(self, page_date: str | None) -> float:
        """Score currency based on how recently the page was updated."""
        if page_date is None:
            return 0.4  # Unknown date = moderate penalty

        try:
            # Try parsing ISO format
            dt = datetime.fromisoformat(page_date.replace("Z", "+00:00"))
        except ValueError:
            try:
                # Try common HTTP date format
                dt = datetime.strptime(page_date, "%a, %d %b %Y %H:%M:%S %Z")
                dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return 0.4

        now = datetime.now(timezone.utc)
        age_days = (now - dt).days

        if age_days < 90:  # < 3 months
            return 1.0
        if age_days < 365:  # < 1 year
            return 0.8
        if age_days < _STALE_THRESHOLD_DAYS:  # < 2 years
            return 0.6
        # Stale
        return 0.3

    def _assess_relevance(self, page_text: str) -> float:
        """Score relevance based on whether content addresses e-filing requirements."""
        text_lower = page_text.lower()
        score = 0.0

        # Primary relevance indicators
        primary_terms = [
            "e-filing", "efiling", "electronic filing",
            "formatting requirement", "document format",
            "proposed order", "court order",
        ]
        primary_hits = sum(1 for term in primary_terms if term in text_lower)
        score += min(0.5, primary_hits * 0.15)

        # Secondary relevance indicators
        secondary_terms = [
            "margin", "font", "page size", "file type",
            "signature", ".docx", ".pdf", "top margin",
            "line spacing", "file format",
        ]
        secondary_hits = sum(1 for term in secondary_terms if term in text_lower)
        score += min(0.3, secondary_hits * 0.06)

        # Jurisdiction-specific terms boost
        jurisdiction_terms = [
            "circuit court", "district court", "supreme court",
            "appellate", "trial court", "family court",
        ]
        jurisdiction_hits = sum(1 for term in jurisdiction_terms if term in text_lower)
        score += min(0.2, jurisdiction_hits * 0.1)

        return round(min(1.0, score), 2)

    def _assess_accuracy(self, page_text: str) -> float:
        """Score accuracy based on specificity of requirements.

        Specific, measurable requirements (e.g., '3-inch top margin')
        score higher than vague guidance (e.g., 'use appropriate margins').
        """
        specific_hits = sum(
            1 for pattern in _SPECIFICITY_PATTERNS
            if re.search(pattern, page_text, re.IGNORECASE)
        )
        vague_hits = sum(
            1 for pattern in _VAGUE_PATTERNS
            if re.search(pattern, page_text, re.IGNORECASE)
        )

        # More specific language = higher accuracy score
        specificity_score = min(1.0, specific_hits * 0.2)
        vagueness_penalty = min(0.3, vague_hits * 0.1)

        return round(max(0.1, specificity_score - vagueness_penalty), 2)

    def cross_reference(
        self,
        requirement: EFilingRequirement,
        other_requirements: list[EFilingRequirement],
    ) -> EFilingRequirement:
        """Cross-reference a requirement against others for the same field.

        If multiple independent sources agree on a value, both sources
        gain corroboration. If they disagree, both are flagged.
        """
        if requirement.reliability is None:
            return requirement

        for other in other_requirements:
            if other.id == requirement.id:
                continue
            if other.field != requirement.field:
                continue
            if other.jurisdiction != requirement.jurisdiction:
                continue
            # Same condition check (e.g., both about proposed orders)
            if other.condition != requirement.condition:
                continue

            if other.value == requirement.value:
                # Agreement: add corroboration
                if other.source_url not in requirement.reliability.corroborated_by:
                    requirement.reliability.corroborated_by.append(other.source_url)
                if other.reliability and requirement.source_url not in other.reliability.corroborated_by:
                    other.reliability.corroborated_by.append(requirement.source_url)
                logger.info(
                    "Corroborated: %s=%s (%s <-> %s)",
                    requirement.field, requirement.value,
                    requirement.source_url, other.source_url,
                )
            else:
                # Disagreement: flag contradiction
                if other.source_url not in requirement.reliability.contradicted_by:
                    requirement.reliability.contradicted_by.append(other.source_url)
                if other.reliability and requirement.source_url not in other.reliability.contradicted_by:
                    other.reliability.contradicted_by.append(requirement.source_url)
                logger.warning(
                    "Contradiction: %s=%s vs %s (%s vs %s)",
                    requirement.field, requirement.value, other.value,
                    requirement.source_url, other.source_url,
                )

        return requirement

    def generate_report(self) -> dict:
        """Generate a reliability summary report for all assessed sources."""
        sources = list(self._source_assessments.values())
        return {
            "total_sources_assessed": len(sources),
            "by_tier": {
                "official": sum(1 for s in sources if s.tier == SourceTier.OFFICIAL),
                "quasi_official": sum(1 for s in sources if s.tier == SourceTier.QUASI_OFFICIAL),
                "secondary": sum(1 for s in sources if s.tier == SourceTier.SECONDARY),
                "tertiary": sum(1 for s in sources if s.tier == SourceTier.TERTIARY),
            },
            "trustworthy_count": sum(1 for s in sources if s.is_trustworthy),
            "needs_verification_count": sum(1 for s in sources if s.needs_verification),
            "average_score": (
                round(sum(s.overall_score for s in sources) / len(sources), 3)
                if sources else 0.0
            ),
            "sources": [
                {
                    "url": s.source_url,
                    "tier": s.tier.value,
                    "score": s.overall_score,
                    "trustworthy": s.is_trustworthy,
                    "needs_verification": s.needs_verification,
                }
                for s in sources
            ],
        }
