namespace LegalEngine.Api

open System
open Microsoft.AspNetCore.Http
open LegalEngine.Domain
open LegalEngine.Rules

/// Handler for POST /analyze/structure — validate document structure.
module ValidateHandler =

    /// POST /analyze/structure handler.
    let handle (req: ValidateRequest) : IResult =
        let jurisdiction = if String.IsNullOrWhiteSpace req.Jurisdiction then "wisconsin" else req.Jurisdiction
        let courtLevel = if String.IsNullOrWhiteSpace req.CourtLevel then "appellate" else req.CourtLevel
        let documentType = if String.IsNullOrWhiteSpace req.DocumentType then "brief" else req.DocumentType
        let variant = if String.IsNullOrWhiteSpace req.Variant then None else Some req.Variant

        try
            let _ruleset = YamlLoader.loadRuleset jurisdiction courtLevel documentType variant

            // TODO: Wire up full parsing + validation pipeline
            // For now, create a minimal document and report no issues
            let doc =
                { LegalDocument.empty with
                    RawText = Some req.Text }

            let issues =
                doc.Issues |> List.map (fun vi ->
                    let (RuleCode code) = vi.Code
                    { Rule = code
                      Severity =
                          match vi.Severity with
                          | Severity.Info -> "info"
                          | Severity.Warning -> "warning"
                          | Severity.Error -> "error"
                      Message = vi.Message
                      SuggestedFix = "" })

            let sections =
                doc.Sections |> List.map (fun s ->
                    { Id = s.Id
                      Heading = s.HeadingText
                      Level = HeadingLevel.toInt s.HeadingLevel
                      IsGenerated = s.IsGenerated
                      ContentLength = s.Content |> List.sumBy (fun b -> b.Text.Length) })

            let response : ValidationResponse =
                { Valid = issues.IsEmpty
                  IssueCount = issues.Length
                  Issues = issues |> Array.ofList
                  Sections = sections |> Array.ofList }
            Results.Ok(response)
        with
        | ex ->
            Results.NotFound({| Error = ex.Message |})
