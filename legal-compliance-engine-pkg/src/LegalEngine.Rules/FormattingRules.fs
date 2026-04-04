namespace LegalEngine.Rules

/// Formatting validation engine.
/// Checks font, margins, spacing, and page/word limits
/// against the ruleset's page format rules.

open LegalEngine.Domain

module FormattingRules =

    /// Check formatting compliance of a document against ruleset page format rules.
    /// Returns a list of findings for any violations detected.
    /// NOTE: Full formatting checks require rendered output metadata (font, margins, etc.)
    /// which may not be available from plain-text parsing. This module validates what
    /// can be checked from the internal document model.
    let checkFormatting (ruleset: Ruleset) (doc: LegalDocument) : Finding list =
        let pf = ruleset.PageFormat
        let findings = System.Collections.Generic.List<Finding>()

        // Check body text alignment
        let expectedAlignment = pf.BodyAlignment.ToLowerInvariant()
        for section in doc.Sections do
            for block in section.Content do
                if block.IsBodyText then
                    let actualAlignment =
                        match block.Alignment with
                        | Alignment.Left -> "left"
                        | Alignment.Right -> "right"
                        | Alignment.Center -> "center"
                        | Alignment.Justify -> "justify"
                    if actualAlignment <> expectedAlignment then
                        findings.Add(
                            Finding.warning "BODY_ALIGNMENT"
                                (sprintf "Body text alignment is '%s' but ruleset requires '%s'."
                                    actualAlignment expectedAlignment))

        // Check indentation on body text
        for section in doc.Sections do
            for block in section.Content do
                if block.IsBodyText && block.IndentInches > 0.0 then
                    // First-line indent check: warn if significantly different from rule
                    let expected = pf.FirstLineIndentInches
                    let diff = abs (block.IndentInches - expected)
                    if diff > 0.25 then
                        findings.Add(
                            Finding.info "INDENT_MISMATCH"
                                (sprintf "Content indent (%.2f\") differs from expected first-line indent (%.2f\")."
                                    block.IndentInches expected))

        // Warn if no sections exist
        if doc.Sections.IsEmpty then
            findings.Add(
                Finding.warning "NO_SECTIONS"
                    "Document contains no sections.")

        // Note: Font, margin, and spacing checks require rendered document metadata
        // (DOCX properties, PDF page dimensions) which are not available from the
        // internal model. Those checks should be performed by the rendering layer.
        // Adding informational findings for documentation:
        findings.Add(
            Finding.info "FORMAT_SPEC"
                (sprintf "Ruleset requires: %s %gpt, %.1f spacing, margins %.2f/%.2f/%.2f/%.2f"
                    pf.FontName pf.FontSizePt pf.LineSpacing
                    pf.MarginTopInches pf.MarginBottomInches
                    pf.MarginLeftInches pf.MarginRightInches))

        findings |> Seq.toList
