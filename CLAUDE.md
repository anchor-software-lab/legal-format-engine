# Legal Format Engine - Development Context

## Architecture
F# (.NET 8) rules-based legal document formatting and compliance engine.
Seven projects in a single solution.

## Key Design Decisions
- F# discriminated unions model the legal domain — impossible states are unrepresentable
- Court rules ALWAYS win over ML-learned preferences (rule hierarchy enforced in F#)
- ML engine (Python, separate repo: anchor-ml-engine) feeds patterns via JSON
- Rules are YAML files — adding jurisdictions requires zero F# code changes
- Every rule is a pure function: ValidationContext -> LegalDocument -> Finding list

## GitHub Organization
- Org: `anchor-software-lab`
- This repo: `anchor-software-lab/legal-format-engine`
- ML engine: `anchor-software-lab/anchor-ml-engine`

## What's Built
- Domain types: Jurisdiction, CourtLevel, FilingType, SectionKind DUs
- Parsing: NumberingUtils, TextUtils, HeadingDetector, SectionBuilder, PlainTextParser
- Ingestion: DocxReader (DocumentFormat.OpenXml), TextNormalizer
- Rules: YamlLoader, SectionRules, HeadingRules, CaptionRules, BoilerplateRules, FormattingRules, RuleEngine
- Rendering: DocxRenderer, MarkdownRenderer
- API: ASP.NET Core with format, validate, caption, rulesets endpoints
- 78 YAML jurisdiction rulesets (50 states + 14 federal)
- Word Add-in (Office.js taskpane)
- 14 domain tests passing
