namespace LegalEngine.Rules

/// Loads ML-learned formatting patterns from JSON files produced by the
/// Python anchor-ml-engine. These patterns represent what the ML system
/// learned from analyzing uploaded briefs.
///
/// The JSON schema matches the Python synthesizer output:
/// {
///   "jurisdiction": "wisconsin",
///   "court_level": "appellate",
///   "document_type": "brief",
///   "document_count": 127,
///   "overall_confidence": 0.91,
///   "patterns": {
///     "font": { "family": "Times New Roman", "size_pt": 13.0, "confidence": 0.94 },
///     "margins": { "top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0, "confidence": 0.91 },
///     ...
///   }
/// }

open System
open System.IO
open System.Text.Json
open System.Text.Json.Serialization
open LegalEngine.Domain


// ── JSON DTOs (match Python ML output schema) ─────────────────────

[<CLIMutable>]
type MlLearnedValue = {
    [<JsonPropertyName("value")>] Value: JsonElement
    [<JsonPropertyName("confidence")>] Confidence: float
    [<JsonPropertyName("sample_count")>] SampleCount: int
    [<JsonPropertyName("agreement")>] Agreement: float
}

[<CLIMutable>]
type MlFontPattern = {
    [<JsonPropertyName("family")>] Family: string
    [<JsonPropertyName("size_pt")>] SizePt: float
    [<JsonPropertyName("confidence")>] Confidence: float
}

[<CLIMutable>]
type MlMarginPattern = {
    [<JsonPropertyName("top")>] Top: float
    [<JsonPropertyName("bottom")>] Bottom: float
    [<JsonPropertyName("left")>] Left: float
    [<JsonPropertyName("right")>] Right: float
    [<JsonPropertyName("confidence")>] Confidence: float
}

[<CLIMutable>]
type MlHeadingStyle = {
    [<JsonPropertyName("level")>] Level: int
    [<JsonPropertyName("case_style")>] CaseStyle: string
    [<JsonPropertyName("alignment")>] Alignment: string
    [<JsonPropertyName("bold")>] Bold: bool
    [<JsonPropertyName("numbering")>] Numbering: string
    [<JsonPropertyName("confidence")>] Confidence: float
}

[<CLIMutable>]
type MlSectionOrder = {
    [<JsonPropertyName("id")>] Id: string
    [<JsonPropertyName("frequency")>] Frequency: float
    [<JsonPropertyName("median_order")>] MedianOrder: int
}

[<CLIMutable>]
type MlPatterns = {
    [<JsonPropertyName("font")>] Font: MlFontPattern
    [<JsonPropertyName("margins")>] Margins: MlMarginPattern
    [<JsonPropertyName("line_spacing")>] LineSpacing: MlLearnedValue
    [<JsonPropertyName("first_line_indent")>] FirstLineIndent: MlLearnedValue
    [<JsonPropertyName("block_quote_indent")>] BlockQuoteIndent: MlLearnedValue
    [<JsonPropertyName("headings")>] Headings: MlHeadingStyle array
    [<JsonPropertyName("section_order")>] SectionOrder: MlSectionOrder array
}

[<CLIMutable>]
type MlPatternFile = {
    [<JsonPropertyName("jurisdiction")>] Jurisdiction: string
    [<JsonPropertyName("court_level")>] CourtLevel: string
    [<JsonPropertyName("document_type")>] DocumentType: string
    [<JsonPropertyName("document_count")>] DocumentCount: int
    [<JsonPropertyName("overall_confidence")>] OverallConfidence: float
    [<JsonPropertyName("learned_at")>] LearnedAt: string
    [<JsonPropertyName("patterns")>] Patterns: MlPatterns
}


// ── Typed domain model for ML patterns ────────────────────────────

/// A single learned value with confidence metadata.
type LearnedValue<'T> = {
    Value: 'T
    Confidence: float
    SampleCount: int
}

/// Complete set of ML-learned patterns for a jurisdiction/court/doctype.
type MlPatternSet = {
    Jurisdiction: string
    CourtLevel: string
    DocumentType: string
    DocumentCount: int
    OverallConfidence: float
    Font: LearnedValue<string> option
    FontSizePt: LearnedValue<float> option
    Margins: LearnedValue<{| Top: float; Bottom: float; Left: float; Right: float |}> option
    LineSpacing: LearnedValue<float> option
    FirstLineIndent: LearnedValue<float> option
    BlockQuoteIndent: LearnedValue<float> option
    HeadingStyles: LearnedValue<HeadingRule> list
    SectionOrder: (string * float) list  // (section_id, frequency)
}

module MlPatternSet =
    let empty = {
        Jurisdiction = ""
        CourtLevel = ""
        DocumentType = ""
        DocumentCount = 0
        OverallConfidence = 0.0
        Font = None
        FontSizePt = None
        Margins = None
        LineSpacing = None
        FirstLineIndent = None
        BlockQuoteIndent = None
        HeadingStyles = []
        SectionOrder = []
    }


// ── Loader ────────────────────────────────────────────────────────

module MlPatternLoader =

    let private jsonOptions =
        let opts = JsonSerializerOptions()
        opts.PropertyNameCaseInsensitive <- true
        opts.AllowTrailingCommas <- true
        opts.ReadCommentHandling <- JsonCommentHandling.Skip
        opts

    /// Convert raw JSON DTO to typed domain model.
    let private mapToPatternSet (raw: MlPatternFile) : MlPatternSet =
        let p = raw.Patterns

        let font =
            if isNull (box p.Font) || String.IsNullOrEmpty(p.Font.Family) then None
            else Some { Value = p.Font.Family; Confidence = p.Font.Confidence; SampleCount = raw.DocumentCount }

        let fontSize =
            if isNull (box p.Font) || p.Font.SizePt <= 0.0 then None
            else Some { Value = p.Font.SizePt; Confidence = p.Font.Confidence; SampleCount = raw.DocumentCount }

        let margins =
            if isNull (box p.Margins) then None
            else Some {
                Value = {| Top = p.Margins.Top; Bottom = p.Margins.Bottom
                           Left = p.Margins.Left; Right = p.Margins.Right |}
                Confidence = p.Margins.Confidence
                SampleCount = raw.DocumentCount
            }

        let lineSpacing =
            if isNull (box p.LineSpacing) then None
            else
                let v = p.LineSpacing.Value
                if v.ValueKind = JsonValueKind.Number then
                    Some { Value = v.GetDouble(); Confidence = p.LineSpacing.Confidence; SampleCount = p.LineSpacing.SampleCount }
                else None

        let firstLineIndent =
            if isNull (box p.FirstLineIndent) then None
            else
                let v = p.FirstLineIndent.Value
                if v.ValueKind = JsonValueKind.Number then
                    Some { Value = v.GetDouble(); Confidence = p.FirstLineIndent.Confidence; SampleCount = p.FirstLineIndent.SampleCount }
                else None

        let headingStyles =
            if isNull (box p.Headings) then []
            else
                p.Headings
                |> Array.toList
                |> List.map (fun h ->
                    { Value = {
                        Level = h.Level
                        CaseStyle = h.CaseStyle
                        Alignment = h.Alignment
                        Numbering = if String.IsNullOrEmpty h.Numbering then None else Some h.Numbering
                        Bold = h.Bold
                        IndentInches = 0.0 }
                      Confidence = h.Confidence
                      SampleCount = raw.DocumentCount })

        let sectionOrder =
            if isNull (box p.SectionOrder) then []
            else
                p.SectionOrder
                |> Array.toList
                |> List.map (fun s -> (s.Id, s.Frequency))

        {
            Jurisdiction = raw.Jurisdiction
            CourtLevel = raw.CourtLevel
            DocumentType = raw.DocumentType
            DocumentCount = raw.DocumentCount
            OverallConfidence = raw.OverallConfidence
            Font = font
            FontSizePt = fontSize
            Margins = margins
            LineSpacing = lineSpacing
            FirstLineIndent = firstLineIndent
            BlockQuoteIndent = None
            HeadingStyles = headingStyles
            SectionOrder = sectionOrder
        }

    /// Load ML patterns from a JSON file.
    let loadFromFile (path: string) : Result<MlPatternSet, string> =
        if not (File.Exists path) then
            Error $"ML pattern file not found: {path}"
        else
            try
                let json = File.ReadAllText(path)
                let raw = JsonSerializer.Deserialize<MlPatternFile>(json, jsonOptions)
                Ok (mapToPatternSet raw)
            with ex ->
                Error $"Failed to parse ML patterns: {ex.Message}"

    /// Load ML patterns from a JSON string.
    let loadFromJson (json: string) : Result<MlPatternSet, string> =
        try
            let raw = JsonSerializer.Deserialize<MlPatternFile>(json, jsonOptions)
            Ok (mapToPatternSet raw)
        with ex ->
            Error $"Failed to parse ML patterns: {ex.Message}"

    /// Try to load patterns for a jurisdiction from a directory.
    let tryLoadForJurisdiction
        (dir: string)
        (jurisdiction: string)
        (courtLevel: string)
        (documentType: string)
        : MlPatternSet option =

        let filename = $"{jurisdiction}_{courtLevel}_{documentType}.json"
        let path = Path.Combine(dir, filename)
        match loadFromFile path with
        | Ok patterns -> Some patterns
        | Error _ -> None
