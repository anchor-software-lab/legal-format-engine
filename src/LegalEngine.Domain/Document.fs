namespace LegalEngine.Domain

/// Internal document representation.
/// All engines operate on this model — parsers produce it, rules validate it,
/// renderers consume it.

type SourceSpan =
    { StartIndex: int
      EndIndex: int
      Page: int option
      Line: int option }

type ContentBlock =
    { Text: string
      Bold: bool
      Italic: bool
      Underline: bool
      Alignment: Alignment
      IsBodyText: bool
      IsCaption: bool
      IndentInches: float }

module ContentBlock =
    let text t =
        { Text = t; Bold = false; Italic = false; Underline = false
          Alignment = Alignment.Justify; IsBodyText = true; IsCaption = false
          IndentInches = 0.0 }

    let caption t bold alignment =
        { Text = t; Bold = bold; Italic = false; Underline = false
          Alignment = alignment; IsBodyText = false; IsCaption = true
          IndentInches = 0.0 }

type Section =
    { Id: string
      HeadingText: string
      HeadingLevel: HeadingLevel
      NumberingPrefix: string option
      Content: ContentBlock list
      Subsections: Section list
      IsGenerated: bool }

module Section =
    let create id heading level content =
        { Id = id; HeadingText = heading; HeadingLevel = level
          NumberingPrefix = None; Content = content
          Subsections = []; IsGenerated = false }

type CaptionBlock =
    { Lines: ContentBlock list }

type SignatureBlockInfo =
    { AttorneyName: string
      BarNumber: string
      Firm: string option
      Address: string
      Phone: string
      Email: string }

[<RequireQualifiedAccess>]
type Severity =
    | Info
    | Warning
    | Error

type RuleCode = RuleCode of string

type ValidationIssue =
    { Severity: Severity
      Code: RuleCode
      Message: string
      SectionId: string option
      AutoFixable: bool }

type LegalDocument =
    { Metadata: Map<string, obj> option
      Caption: CaptionBlock option
      Sections: Section list
      SignatureBlock: SignatureBlockInfo option
      Certifications: Section list
      Issues: ValidationIssue list
      RawText: string option }

module LegalDocument =
    let empty =
        { Metadata = None; Caption = None; Sections = []
          SignatureBlock = None; Certifications = []
          Issues = []; RawText = None }
