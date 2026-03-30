# Legal Format Engine - Development Context

## Previous Session Transcript
Full conversation history is at `docs/transcripts/session-2026-03-30-initial-build.jsonl`
Read this JSONL file to understand all design decisions, user requirements, and implementation history.

## Architecture Summary
Rules-based legal document formatting engine. Five layers:
1. **Input** - accepts pasted text, DOCX, PDF uploads
2. **Rules** - YAML-based declarative rulesets per jurisdiction/court
3. **Parser** - converts messy documents to structured internal model
4. **Formatter/Validator** - enforces rules deterministically
5. **Output** - DOCX, Markdown, HTML rendering

## ML Pipeline
- `src/legal_format_engine/ml/` - normalizer, feature extractor, learner, synthesizer
- Documents are normalized to remove format-specific quirks before learning
- Rule hierarchy: Court Rules > ML Learned Patterns > Style Profiles > Defaults
- Author/firm attribution auto-detected from signature blocks, metadata, letterhead
- Firm database: 160+ firms pre-loaded with fuzzy matching

## Key Design Decisions
- Court rules ALWAYS win over ML-learned preferences
- ML only fills discretionary gaps (indent depth, block quote style, etc.)
- DOCX output must match real filed briefs exactly (see reference/briefs/)
- Wisconsin appellate brief is the starting market (derived from actual SPD filings)
- 64 jurisdiction rulesets (50 states + 14 federal courts)
- Word Add-in is the primary distribution channel

## GitHub Organization
- Org: `anchor-software-lab` (the software company)
- Repo: `anchor-software-lab/legal-format-engine`
- Development branch: `claude/legal-rules-engine-T9ZP3`

## What's Working (514 tests)
- Caption engine, heading normalizer, section validator/reorderer
- Boilerplate generator (signature blocks, certifications)
- DOCX/PDF/plain text parsers
- DOCX/Markdown renderers with proper formatting (first-line indent, caption layout, hyphenation)
- Wisconsin appellate brief ruleset (derived from real Christopherson brief)
- 63 additional jurisdiction rulesets
- ML pipeline (normalize, extract, learn, synthesize)
- Firm database + auto-attribution
- Archive ingestion (ZIP, RAR, Adobe Portfolio)
- FastAPI server + Word Add-in
- Letterhead system

## What Needs Work Next
- More DOCX formatting refinements (Century Schoolbook font, block quote indentation)
- Upload more reference briefs to refine ML
- Citation consistency engine improvements
- Cloud deployment (Railway/Render/Azure)
- Microsoft Store submission path
- anchor-filings-website repo needs real website content
