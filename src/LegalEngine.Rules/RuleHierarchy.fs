namespace LegalEngine.Rules

/// Enforces the strict formatting rule hierarchy:
///
///   1. Court Rules (YAML rulesets)  — MANDATORY, never overridden
///   2. ML Learned Patterns (JSON)   — fills discretionary gaps only
///   3. Style Profiles (per-firm)    — lowest priority override
///   4. Engine Defaults              — fallback for everything else
///
/// The court rules are the floor. ML can refine within them but never violate.
/// A formatting decision is "discretionary" if the court rule does not specify it.

open LegalEngine.Domain


/// Where a formatting decision came from.
[<RequireQualifiedAccess>]
type DecisionSource =
    | CourtRule        // Mandatory — from YAML ruleset
    | MlLearned        // Advisory — from ML pattern analysis
    | StyleProfile     // Preference — from firm/author style
    | Default          // Fallback — engine default

/// A single formatting decision with provenance.
type FormattingDecision = {
    Field: string
    Value: obj
    Source: DecisionSource
    Confidence: float
    Explanation: string
}

/// Fully resolved format with provenance for every decision.
type ResolvedFormat = {
    Jurisdiction: string
    CourtLevel: string
    DocumentType: string
    Decisions: FormattingDecision list
    PageFormat: PageFormat
    HeadingRules: HeadingRule list
}


/// Style profile for a firm or author (matches ML engine output).
type StyleProfile = {
    Identifier: string
    ProfileType: string  // "author" or "firm"
    FirstLineIndent: float option
    BlockQuoteIndent: float option
    SectionSpacing: float option
    Justify: bool option
    DocumentCount: int
    Confidence: float
}

module StyleProfile =
    let empty = {
        Identifier = ""
        ProfileType = "author"
        FirstLineIndent = None
        BlockQuoteIndent = None
        SectionSpacing = None
        Justify = None
        DocumentCount = 0
        Confidence = 0.0
    }


module RuleHierarchy =

    /// Resolve the final formatting by applying the 4-tier hierarchy.
    /// Court rules always win. ML fills gaps. Style profiles are lowest override. Defaults are fallback.
    let resolve
        (ruleset: Ruleset)
        (mlPatterns: MlPatternSet option)
        (styleProfile: StyleProfile option)
        : ResolvedFormat =

        let decisions = ResizeArray<FormattingDecision>()

        // Start with defaults
        let mutable pageFormat = PageFormat.defaults

        // ── Layer 4: Engine Defaults (already set) ──

        // ── Layer 3: Style Profile (overrides defaults for discretionary fields) ──
        match styleProfile with
        | Some style ->
            match style.FirstLineIndent with
            | Some indent ->
                pageFormat <- { pageFormat with FirstLineIndentInches = indent }
                decisions.Add {
                    Field = "first_line_indent_inches"
                    Value = indent
                    Source = DecisionSource.StyleProfile
                    Confidence = style.Confidence
                    Explanation = $"Style profile '{style.Identifier}' prefers {indent}\" indent"
                }
            | None -> ()
        | None -> ()

        // ── Layer 2: ML Learned Patterns (overrides style for discretionary fields) ──
        match mlPatterns with
        | Some ml ->
            // First-line indent (discretionary — ML can override)
            match ml.FirstLineIndent with
            | Some learned when learned.Confidence >= 0.5 ->
                pageFormat <- { pageFormat with FirstLineIndentInches = learned.Value }
                decisions.Add {
                    Field = "first_line_indent_inches"
                    Value = learned.Value
                    Source = DecisionSource.MlLearned
                    Confidence = learned.Confidence
                    Explanation = $"ML learned {learned.Value}\" indent from {learned.SampleCount} documents"
                }
            | _ -> ()

            // Block quote indent (discretionary)
            match ml.BlockQuoteIndent with
            | Some learned when learned.Confidence >= 0.5 ->
                decisions.Add {
                    Field = "block_quote_indent_inches"
                    Value = learned.Value
                    Source = DecisionSource.MlLearned
                    Confidence = learned.Confidence
                    Explanation = $"ML learned {learned.Value}\" block quote indent"
                }
            | _ -> ()
        | None -> ()

        // ── Layer 1: Court Rules (MANDATORY — overrides EVERYTHING) ──
        let courtFormat = ruleset.PageFormat

        // Font — court rule always wins
        pageFormat <- { pageFormat with FontName = courtFormat.FontName }
        decisions.Add {
            Field = "font_name"; Value = courtFormat.FontName
            Source = DecisionSource.CourtRule; Confidence = 1.0
            Explanation = "Court rule requires this font"
        }

        pageFormat <- { pageFormat with FontSizePt = courtFormat.FontSizePt }
        decisions.Add {
            Field = "font_size_pt"; Value = courtFormat.FontSizePt
            Source = DecisionSource.CourtRule; Confidence = 1.0
            Explanation = "Court rule requires this font size"
        }

        // Line spacing — court rule
        pageFormat <- { pageFormat with LineSpacing = courtFormat.LineSpacing }
        decisions.Add {
            Field = "line_spacing"; Value = courtFormat.LineSpacing
            Source = DecisionSource.CourtRule; Confidence = 1.0
            Explanation = "Court rule requires this line spacing"
        }

        // Margins — court rule
        pageFormat <- { pageFormat with
                            MarginTopInches = courtFormat.MarginTopInches
                            MarginBottomInches = courtFormat.MarginBottomInches
                            MarginLeftInches = courtFormat.MarginLeftInches
                            MarginRightInches = courtFormat.MarginRightInches }
        decisions.Add {
            Field = "margins"; Value = "court-mandated"
            Source = DecisionSource.CourtRule; Confidence = 1.0
            Explanation = $"Court rule: T={courtFormat.MarginTopInches}\" B={courtFormat.MarginBottomInches}\" L={courtFormat.MarginLeftInches}\" R={courtFormat.MarginRightInches}\""
        }

        // Page dimensions — court rule
        pageFormat <- { pageFormat with
                            PageWidthInches = courtFormat.PageWidthInches
                            PageHeightInches = courtFormat.PageHeightInches }

        // Body alignment — court rule
        pageFormat <- { pageFormat with BodyAlignment = courtFormat.BodyAlignment }

        // First-line indent: court rule wins ONLY if it explicitly sets a value
        // If the court rule uses the default (0.5), ML/style can override
        // This is the "discretionary gap" concept
        if courtFormat.FirstLineIndentInches <> PageFormat.defaults.FirstLineIndentInches then
            pageFormat <- { pageFormat with FirstLineIndentInches = courtFormat.FirstLineIndentInches }
            decisions.Add {
                Field = "first_line_indent_inches"
                Value = courtFormat.FirstLineIndentInches
                Source = DecisionSource.CourtRule
                Confidence = 1.0
                Explanation = "Court rule explicitly sets first-line indent"
            }

        // Heading rules: court rules always win
        let headingRules = ruleset.HeadingRules

        // ML heading styles are advisory — only produce INFO findings, never override
        match mlPatterns with
        | Some ml ->
            for learned in ml.HeadingStyles do
                let courtRule = headingRules |> List.tryFind (fun r -> r.Level = learned.Value.Level)
                match courtRule with
                | Some cr when cr.CaseStyle <> learned.Value.CaseStyle && learned.Confidence >= 0.7 ->
                    decisions.Add {
                        Field = $"heading_level_{learned.Value.Level}_case_style"
                        Value = learned.Value.CaseStyle
                        Source = DecisionSource.MlLearned
                        Confidence = learned.Confidence
                        Explanation = $"ML suggests '{learned.Value.CaseStyle}' but court rule requires '{cr.CaseStyle}' — court rule wins"
                    }
                | _ -> ()
        | None -> ()

        {
            Jurisdiction = ruleset.Jurisdiction
            CourtLevel = ruleset.CourtLevel
            DocumentType = ruleset.DocumentType
            Decisions = decisions |> Seq.toList
            PageFormat = pageFormat
            HeadingRules = headingRules
        }

    /// Check if a field is governed by court rules (mandatory) or discretionary.
    let isDiscretionary (field: string) : bool =
        let mandatoryFields = set [
            "font_name"; "font_size_pt"; "line_spacing"
            "margin_top_inches"; "margin_bottom_inches"
            "margin_left_inches"; "margin_right_inches"
            "page_width_inches"; "page_height_inches"
        ]
        not (mandatoryFields.Contains field)
