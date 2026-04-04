namespace LegalEngine.Rules

/// Boilerplate block generation engine.
/// Generates signature blocks, certifications, and other standard blocks
/// from metadata and ruleset templates.

open System
open LegalEngine.Domain

module BoilerplateRules =

    // ── Template Rendering ──────────────────────────────────────────

    /// Build the template variable dictionary for certification/signature rendering.
    let private buildTemplateVars
        (metadata: DocumentMetadata)
        (filed: DateTime)
        (wordCount: int option)
        (serviceParties: string option)
        : Map<string, string> =
        Map.ofList
            [ "attorney_name", metadata.Attorney.Name
              "bar_number", metadata.Attorney.BarNumber
              "firm", (metadata.Attorney.Firm |> Option.defaultValue "")
              "address", metadata.Attorney.Address
              "phone", metadata.Attorney.Phone
              "email", metadata.Attorney.Email
              "date_filed", filed.ToString("MMMM dd, yyyy")
              "day", string filed.Day
              "month", filed.ToString("MMMM")
              "year", string filed.Year
              "word_count", (wordCount |> Option.map string |> Option.defaultValue "[WORD COUNT]")
              "service_parties", (serviceParties |> Option.defaultValue "[SERVICE PARTIES]")
              "signature_line", "____________________________"
              "case_number", metadata.Case.CaseNumber ]

    /// Render a template string by substituting {variable} placeholders.
    /// Missing keys produce [KEY_NAME] placeholder text instead of errors.
    let private renderTemplate (template: string) (variables: Map<string, string>) : string =
        let mutable result = template
        // Replace all {key} patterns
        let regex = System.Text.RegularExpressions.Regex(@"\{(\w+)\}")
        result <-
            regex.Replace(result, fun m ->
                let key = m.Groups.[1].Value
                match Map.tryFind key variables with
                | Some value -> value
                | None -> sprintf "[%s]" (key.ToUpperInvariant()))
        result

    // ── Signature Block ─────────────────────────────────────────────

    /// Generate a signature block from attorney metadata.
    let generateSignatureBlock (metadata: DocumentMetadata) : SignatureBlockInfo =
        { AttorneyName = metadata.Attorney.Name
          BarNumber = metadata.Attorney.BarNumber
          Firm = metadata.Attorney.Firm
          Address = metadata.Attorney.Address
          Phone = metadata.Attorney.Phone
          Email = metadata.Attorney.Email }

    // ── Certifications ──────────────────────────────────────────────

    /// Generate certification sections from templates.
    /// Each CertificationRule produces a Section with the rendered template.
    let generateCertifications
        (metadata: DocumentMetadata)
        (rules: CertificationRule list)
        (wordCount: int option)
        (serviceParties: string option)
        : Section list =

        let filed =
            metadata.DateFiled
            |> Option.defaultValue DateTime.Today

        let templateVars = buildTemplateVars metadata filed wordCount serviceParties

        rules
        |> List.map (fun rule ->
            let text = renderTemplate rule.Template templateVars
            let headingText =
                match rule.Title with
                | Some title -> title.ToUpperInvariant()
                | None -> rule.Id.Replace("_", " ").ToUpperInvariant()
            { Id = rule.Id
              HeadingText = headingText
              HeadingLevel = HeadingLevel.Level1
              NumberingPrefix = None
              Content =
                [ { Text = text
                    Bold = false
                    Italic = false
                    Underline = false
                    Alignment = Alignment.Justify
                    IsBodyText = true
                    IsCaption = false
                    IndentInches = 0.0 } ]
              Subsections = []
              IsGenerated = true })
