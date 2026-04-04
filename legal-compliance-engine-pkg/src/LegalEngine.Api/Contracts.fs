namespace LegalEngine.Api

/// Request/response DTOs for the legal compliance engine API.
/// [<CLIMutable>] enables JSON deserialization with System.Text.Json.

[<CLIMutable>]
type FormatRequest =
    { Text: string
      Jurisdiction: string
      CourtLevel: string
      DocumentType: string
      Variant: string
      OutputFormat: string
      InsertMissing: bool }

[<CLIMutable>]
type ValidateRequest =
    { Text: string
      Jurisdiction: string
      CourtLevel: string
      DocumentType: string
      Variant: string }

[<CLIMutable>]
type CaptionRequest =
    { CourtName: string
      CaseNumber: string
      Parties: CaptionPartyDto array
      DocumentTitle: string
      Jurisdiction: string
      CourtLevel: string }

and [<CLIMutable>] CaptionPartyDto =
    { Name: string
      Role: string
      Designation: string }

[<CLIMutable>]
type FindingResponse =
    { Rule: string
      Severity: string
      Message: string
      SuggestedFix: string }

[<CLIMutable>]
type SectionSummary =
    { Id: string
      Heading: string
      Level: int
      IsGenerated: bool
      ContentLength: int }

[<CLIMutable>]
type ValidationResponse =
    { Valid: bool
      IssueCount: int
      Issues: FindingResponse array
      Sections: SectionSummary array }

[<CLIMutable>]
type FormatResponse =
    { Markdown: string
      IssueCount: int
      Issues: FindingResponse array
      Sections: SectionSummary array }

[<CLIMutable>]
type HealthResponse =
    { Status: string
      Version: string }

[<CLIMutable>]
type CaptionResponse =
    { CaptionText: string
      Lines: string array }

[<CLIMutable>]
type RulesetResponse =
    { Jurisdiction: string
      CourtLevel: string
      DocumentType: string
      FontName: string
      FontSizePt: float
      LineSpacing: float
      MarginTopInches: float
      MarginBottomInches: float
      MarginLeftInches: float
      MarginRightInches: float
      RequiredSectionCount: int
      HeadingRuleCount: int }
