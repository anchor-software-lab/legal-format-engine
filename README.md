# Legal Format Engine

Rules-based legal document formatting and compliance engine built in F#.

A legal control system that catches errors, enforces structure, and uses AI only where judgment is fuzzy.

## Architecture

- **LegalEngine.Domain** — Typed discriminated unions for jurisdictions, courts, filings, sections
- **LegalEngine.Parsing** — Text utilities, heading detection, section building, plain text parser
- **LegalEngine.Ingestion** — DOCX reader (DocumentFormat.OpenXml), PDF reader, text normalizer
- **LegalEngine.Rules** — YAML ruleset loader, section/heading/caption/boilerplate/formatting rules, rule engine
- **LegalEngine.Rendering** — DOCX and Markdown output renderers
- **LegalEngine.Api** — ASP.NET Core API with Word Add-in support

## Build

```bash
dotnet build
dotnet test
dotnet run --project src/LegalEngine.Api
```

## Rulesets

78 YAML rulesets covering all 50 US states + 14 federal courts (SCOTUS + all circuits).
