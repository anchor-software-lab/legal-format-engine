"""Core domain types for the quality gate.

Every type here is Pydantic v2 so it round-trips cleanly through the
SaaS API surface and the plugin clients (whose TypeScript / C# clients
are generated from the same JSON schemas).

Design notes:

- Plaintext document content lives in encrypted blobs, never in these
  metadata records. `Segment.text_hash` references the content; the
  range and text itself are looked up at processing time via
  `CheckContext.get_text(segment)`.
- Every `Finding` carries a `provenance` field describing how it was
  produced (rule, ML, LLM, or hybrid). This preserves the discipline
  established by `legal_format_engine.merge_with_rules`, which already
  emits a `_provenance` map.
- `rule_id` is a stable string taxonomy (`FORMAT.FONT.SIZE`,
  `BB.SIGNAL.UNDERLINE`, `CITE.GHOST`, …). New rules add new IDs;
  existing IDs are never reused for different semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Provenance(str, Enum):
    RULE = "rule"
    ML = "ml"
    LLM = "llm"
    HYBRID = "hybrid"


class Capability(str, Enum):
    NETWORK = "network"
    LLM = "llm"
    AUTHORITY_DB = "authority_db"


class SegmentKind(str, Enum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    FOOTNOTE = "footnote"
    BLOCK_QUOTE = "block_quote"
    TABLE_CELL = "table_cell"


class SuggestionKind(str, Enum):
    REPLACE = "replace"
    INSERT = "insert"
    DELETE = "delete"
    REFORMAT = "reformat"


class CharRange(BaseModel):
    """A character range within a Document, addressed by segment + offsets."""

    model_config = ConfigDict(frozen=True)

    segment_id: str
    start: int
    end: int


class ObservedStyle(BaseModel):
    """Style properties observed on a Segment.

    Field names mirror the keys produced by
    `legal_format_engine.merge_with_rules` so the diff is direct.
    """

    font_name: str | None = None
    font_size_pt: float | None = None
    line_spacing: float | None = None
    alignment: str | None = None
    indent_inches: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    margin_top_inches: float | None = None
    margin_bottom_inches: float | None = None
    margin_left_inches: float | None = None
    margin_right_inches: float | None = None


class Segment(BaseModel):
    """A logical unit of a Document — heading, paragraph, footnote, etc.

    `text_hash` references the segment's content. The plaintext itself
    lives in an encrypted blob; checkers retrieve it via
    `CheckContext.get_text(segment)`.
    """

    id: str
    kind: SegmentKind
    ordinal: int
    text_hash: str
    char_length: int
    style_observed: ObservedStyle = Field(default_factory=ObservedStyle)
    citation_span_ids: list[str] = Field(default_factory=list)


class ParsedCitation(BaseModel):
    case_name: str | None = None
    reporter: str | None = None
    volume: int | None = None
    page: int | None = None
    court: str | None = None
    year: int | None = None
    pinpoint: str | None = None
    signal: str | None = None
    parenthetical: str | None = None
    short_form_of: str | None = None


class Citation(BaseModel):
    id: str
    raw_text: str
    span: CharRange
    parsed: ParsedCitation = Field(default_factory=ParsedCitation)
    normalized: str | None = None
    authority_ref: str | None = None
    confidence: float = 0.0


class Document(BaseModel):
    id: str
    source_uri: str | None = None
    mime: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    sha256: str
    parsed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    jurisdiction_hints: list[str] = Field(default_factory=list)
    doc_type: str | None = None
    segments: list[Segment] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class TreatmentSignal(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    DISTINGUISHING = "distinguishing"


class GoodLawStatus(str, Enum):
    GOOD_LAW = "good_law"
    QUESTIONED = "questioned"
    OVERRULED = "overruled"
    REVERSED = "reversed"
    VACATED = "vacated"
    SUPERSEDED = "superseded"


class Treatment(BaseModel):
    citing_authority_id: str
    signal: TreatmentSignal
    depth: int = 1
    source: str = "courtlistener"
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Authority(BaseModel):
    id: str
    canonical_cite: str
    name: str | None = None
    court: str | None = None
    decided: datetime | None = None
    parallel_cites: list[str] = Field(default_factory=list)
    treatments: list[Treatment] = Field(default_factory=list)
    current_status: GoodLawStatus = GoodLawStatus.GOOD_LAW
    last_verified: datetime | None = None


class Suggestion(BaseModel):
    kind: SuggestionKind
    range: CharRange
    new_text: str | None = None
    new_style: ObservedStyle | None = None
    rationale: str
    auto_apply_safe: bool = False


class Finding(BaseModel):
    id: str
    segment_id: str
    checker_id: str
    rule_id: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    suggestion: Suggestion | None = None
    confidence: float = 1.0
    provenance: Provenance = Provenance.RULE


class LLMCostBreakdown(BaseModel):
    total_usd_cents: int = 0
    by_prompt: dict[str, int] = Field(default_factory=dict)
    by_provider: dict[str, int] = Field(default_factory=dict)


class QualityReport(BaseModel):
    document_id: str
    run_id: str
    findings: list[Finding] = Field(default_factory=list)
    score: float = 100.0
    applied_suggestions: list[str] = Field(default_factory=list)
    remaining_findings: list[str] = Field(default_factory=list)
    cost: LLMCostBreakdown = Field(default_factory=LLMCostBreakdown)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
