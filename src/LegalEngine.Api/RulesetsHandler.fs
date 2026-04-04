namespace LegalEngine.Api

open Microsoft.AspNetCore.Http
open LegalEngine.Rules

/// Handlers for ruleset lookup and health check.
module RulesetsHandler =

    /// GET /rules/{jurisdiction}/{filingType} handler.
    let handleGetRuleset (jurisdiction: string) (filingType: string) : IResult =
        // filingType maps to courtLevel + documentType; use a simple convention for now
        let courtLevel = "appellate"
        let documentType = filingType

        try
            let ruleset = YamlLoader.loadRuleset jurisdiction courtLevel documentType None
            let response : RulesetResponse =
                { Jurisdiction = ruleset.Jurisdiction
                  CourtLevel = ruleset.CourtLevel
                  DocumentType = ruleset.DocumentType
                  FontName = ruleset.PageFormat.FontName
                  FontSizePt = ruleset.PageFormat.FontSizePt
                  LineSpacing = ruleset.PageFormat.LineSpacing
                  MarginTopInches = ruleset.PageFormat.MarginTopInches
                  MarginBottomInches = ruleset.PageFormat.MarginBottomInches
                  MarginLeftInches = ruleset.PageFormat.MarginLeftInches
                  MarginRightInches = ruleset.PageFormat.MarginRightInches
                  RequiredSectionCount = ruleset.RequiredSections.Length
                  HeadingRuleCount = ruleset.HeadingRules.Length }
            Results.Ok(response)
        with
        | ex ->
            Results.NotFound({| Error = ex.Message |})

    /// GET /health handler.
    let handleHealth () : IResult =
        let response : HealthResponse =
            { Status = "ok"
              Version = "0.1.0" }
        Results.Ok(response)
