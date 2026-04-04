namespace LegalEngine.Rules

/// Heading normalization engine.
/// Applies case transformation, regenerates numbering prefixes,
/// and sets heading levels based on the ruleset's heading rules.

open System.Globalization
open LegalEngine.Domain

module HeadingRules =

    // ── Text Utilities (inline until Parsing project is ready) ──────

    /// Strip any existing numbering prefix from a heading.
    /// Handles Roman numerals (I., II., III.), alpha (A., B.), arabic (1., 2.),
    /// and parenthesized variants.
    let private stripNumberingPrefix (text: string) : string =
        if System.String.IsNullOrWhiteSpace text then text
        else
            // TODO: Delegate to LegalEngine.Parsing.NumberingUtils when available
            let pattern = @"^\s*(?:[IVXLCDM]+\.|[A-Z]\.|[a-z]\.|[0-9]+\.|\([0-9]+\)|\([a-z]\))\s*"
            System.Text.RegularExpressions.Regex.Replace(text, pattern, "").Trim()

    /// Generate a numbering prefix for the given 1-based index and numbering type.
    let private generatePrefix (index: int) (numbering: string option) : string option =
        // TODO: Delegate to LegalEngine.Parsing.NumberingUtils when available
        match numbering with
        | None | Some "" -> None
        | Some "roman" ->
            let roman =
                match index with
                | 1 -> "I" | 2 -> "II" | 3 -> "III" | 4 -> "IV"
                | 5 -> "V" | 6 -> "VI" | 7 -> "VII" | 8 -> "VIII"
                | 9 -> "IX" | 10 -> "X" | 11 -> "XI" | 12 -> "XII"
                | 13 -> "XIII" | 14 -> "XIV" | 15 -> "XV"
                | 16 -> "XVI" | 17 -> "XVII" | 18 -> "XVIII"
                | 19 -> "XIX" | 20 -> "XX"
                | n -> string n  // fallback for very deep nesting
            Some (roman + ".")
        | Some "alpha_upper" ->
            if index >= 1 && index <= 26 then
                Some (string (char (int 'A' + index - 1)) + ".")
            else
                Some (string index + ".")
        | Some "alpha_lower" ->
            if index >= 1 && index <= 26 then
                Some (string (char (int 'a' + index - 1)) + ".")
            else
                Some (string index + ".")
        | Some "arabic" ->
            Some (string index + ".")
        | Some _ -> None

    // ── Case Transformations ────────────────────────────────────────

    /// Convert text to UPPER CASE.
    let private toUpper (text: string) = text.ToUpperInvariant()

    /// Convert text to Title Case.
    let private toTitleCase (text: string) =
        // TODO: Delegate to LegalEngine.Parsing.TextUtils when available
        let ti = CultureInfo.InvariantCulture.TextInfo
        ti.ToTitleCase(text.ToLowerInvariant())

    /// Convert text to Sentence case (first letter upper, rest lower).
    let private toSentenceCase (text: string) =
        if System.String.IsNullOrWhiteSpace text then text
        else
            let lower = text.ToLowerInvariant()
            string (System.Char.ToUpperInvariant(lower.[0])) + lower.[1..]

    /// Apply a case transformation based on CaseStyle string.
    let private applyCase (caseStyle: string) (text: string) : string =
        match caseStyle with
        | "upper" -> toUpper text
        | "title" -> toTitleCase text
        | "sentence" -> toSentenceCase text
        | _ -> text

    // ── Heading Normalization ───────────────────────────────────────

    /// Normalize headings at a specific level among siblings.
    let private normalizeLevel (level: int) (ruleset: Ruleset) (sections: Section list) : Section list =
        match Ruleset.getHeadingRule level ruleset with
        | None -> sections
        | Some rule ->
            sections
            |> List.mapi (fun i section ->
                let bareText = stripNumberingPrefix section.HeadingText
                let normalized = applyCase rule.CaseStyle bareText
                let prefix = generatePrefix (i + 1) rule.Numbering
                let headingLevel =
                    HeadingLevel.fromInt level
                    |> Option.defaultValue section.HeadingLevel
                { section with
                    HeadingText = normalized
                    HeadingLevel = headingLevel
                    NumberingPrefix = prefix })

    /// Recursively normalize subsections at deeper levels.
    let private normalizeSubsections (ruleset: Ruleset) (section: Section) : Section =
        let normalizedSubs =
            section.Subsections
            |> normalizeLevel 2 ruleset
            |> List.map (fun sub ->
                let normalizedSubSubs =
                    sub.Subsections
                    |> normalizeLevel 3 ruleset
                    |> List.map (fun subsub ->
                        let normalizedSubSubSubs =
                            subsub.Subsections
                            |> normalizeLevel 4 ruleset
                        { subsub with Subsections = normalizedSubSubSubs })
                { sub with Subsections = normalizedSubSubs })
        { section with Subsections = normalizedSubs }

    /// Normalize all headings in a section list according to ruleset rules.
    /// Applies case transformation, regenerates numbering prefixes,
    /// and processes all nesting levels (1-4).
    let normalizeHeadings (ruleset: Ruleset) (sections: Section list) : Section list =
        sections
        |> normalizeLevel 1 ruleset
        |> List.map (normalizeSubsections ruleset)
