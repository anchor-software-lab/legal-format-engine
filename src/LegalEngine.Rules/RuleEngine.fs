namespace LegalEngine.Rules

/// Document formatting pipeline orchestrator.
/// Runs the full formatting flow: validate -> reorder -> normalize -> caption -> boilerplate.
/// Also provides rule composition utilities.

open LegalEngine.Domain

module RuleEngine =

    /// Run the full formatting pipeline on a document.
    ///
    /// Steps:
    /// 1. Validate sections against ruleset
    /// 2. Reorder sections to canonical order
    /// 3. Insert stubs for missing required sections (optional)
    /// 4. Normalize headings
    /// 5. Generate caption from metadata
    /// 6. Generate signature block and certifications
    /// 7. Check formatting compliance
    ///
    /// Returns the formatted document and all validation findings.
    let formatDocument
        (metadata: DocumentMetadata)
        (ruleset: Ruleset)
        (wordCount: int option)
        (serviceParties: string option)
        (insertMissing: bool)
        (doc: LegalDocument)
        : LegalDocument * Finding list =

        // Step 1: Validate sections
        let sectionFindings = SectionRules.validateSections ruleset doc

        // Step 2: Reorder sections
        let reorderedSections = SectionRules.reorderSections ruleset doc.Sections

        // Step 3: Insert missing stubs
        let sectionsWithStubs =
            if insertMissing then
                SectionRules.insertMissingSections ruleset reorderedSections
            else
                reorderedSections

        // Step 4: Normalize headings
        let normalizedSections = HeadingRules.normalizeHeadings ruleset sectionsWithStubs

        // Step 5: Generate caption
        let caption = CaptionRules.generateCaption metadata ruleset.CaptionRule

        // Step 6: Generate boilerplate
        let signatureBlock = BoilerplateRules.generateSignatureBlock metadata
        let certifications =
            BoilerplateRules.generateCertifications metadata ruleset.Certifications wordCount serviceParties

        // Step 7: Check formatting
        let updatedDoc =
            { doc with
                Sections = normalizedSections
                Caption = Some caption
                SignatureBlock = Some signatureBlock
                Certifications = certifications }

        let formattingFindings = FormattingRules.checkFormatting ruleset updatedDoc

        let allFindings = sectionFindings @ formattingFindings

        updatedDoc, allFindings

    /// Compose multiple Rule functions into a single Rule.
    /// Each rule is applied and all findings are collected.
    let composeRules (rules: Rule list) : Rule =
        fun ctx doc ->
            rules |> List.collect (fun rule -> rule ctx doc)

    /// Create a validation Rule from the section validation logic.
    let sectionValidationRule (ruleset: Ruleset) : Rule =
        fun _ctx doc ->
            SectionRules.validateSections ruleset doc

    /// Create a validation Rule from the formatting check logic.
    let formattingValidationRule (ruleset: Ruleset) : Rule =
        fun _ctx doc ->
            FormattingRules.checkFormatting ruleset doc

    /// Create a combined validation Rule that checks both sections and formatting.
    let fullValidationRule (ruleset: Ruleset) : Rule =
        composeRules
            [ sectionValidationRule ruleset
              formattingValidationRule ruleset ]
