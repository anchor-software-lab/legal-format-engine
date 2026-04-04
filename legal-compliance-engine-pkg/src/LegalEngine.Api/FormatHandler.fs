namespace LegalEngine.Api

open System
open System.IO
open Microsoft.AspNetCore.Http
open LegalEngine.Domain
open LegalEngine.Rendering
open LegalEngine.Rules

/// Handler for POST /analyze/filing — format a legal document.
module FormatHandler =

    let private toSectionSummary (s: Section) : SectionSummary =
        { Id = s.Id
          Heading = s.HeadingText
          Level = HeadingLevel.toInt s.HeadingLevel
          IsGenerated = s.IsGenerated
          ContentLength = s.Content |> List.sumBy (fun b -> b.Text.Length) }

    /// POST /analyze/filing handler.
    let handle (req: FormatRequest) : IResult =
        let jurisdiction = if String.IsNullOrWhiteSpace req.Jurisdiction then "wisconsin" else req.Jurisdiction
        let courtLevel = if String.IsNullOrWhiteSpace req.CourtLevel then "appellate" else req.CourtLevel
        let documentType = if String.IsNullOrWhiteSpace req.DocumentType then "brief" else req.DocumentType
        let variant = if String.IsNullOrWhiteSpace req.Variant then None else Some req.Variant

        try
            let ruleset = YamlLoader.loadRuleset jurisdiction courtLevel documentType variant

            // TODO: Wire up full parsing pipeline (parse text -> LegalDocument -> validate -> format)
            // For now, create a minimal document from the raw text
            let doc =
                { LegalDocument.empty with
                    RawText = Some req.Text }

            let outputFormat =
                if String.IsNullOrWhiteSpace req.OutputFormat then "markdown"
                else req.OutputFormat.ToLowerInvariant()

            if outputFormat = "docx" then
                let tempPath = Path.Combine(Path.GetTempPath(), sprintf "legal_%s.docx" (Guid.NewGuid().ToString("N")))
                DocxRenderer.renderDocx doc ruleset tempPath
                Results.File(tempPath, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "formatted_brief.docx")
            else
                let md = MarkdownRenderer.renderMarkdown doc
                let issues = doc.Issues |> List.map (fun vi ->
                    let (RuleCode code) = vi.Code
                    { Rule = code
                      Severity =
                          match vi.Severity with
                          | Severity.Info -> "info"
                          | Severity.Warning -> "warning"
                          | Severity.Error -> "error"
                      Message = vi.Message
                      SuggestedFix = "" })
                let sections = doc.Sections |> List.map toSectionSummary
                let response : FormatResponse =
                    { Markdown = md
                      IssueCount = issues.Length
                      Issues = issues |> Array.ofList
                      Sections = sections |> Array.ofList }
                Results.Ok(response)
        with
        | ex ->
            Results.NotFound({| Error = ex.Message |})
