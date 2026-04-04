namespace LegalEngine.Domain

/// Structured findings from rule validation.
/// Every finding is typed — no vibes, no loose strings.

type Finding =
    { Rule: RuleCode
      Severity: Severity
      Message: string
      Location: SourceSpan option
      SuggestedFix: string option }

module Finding =
    let error code msg =
        { Rule = RuleCode code; Severity = Severity.Error
          Message = msg; Location = None; SuggestedFix = None }

    let warning code msg =
        { Rule = RuleCode code; Severity = Severity.Warning
          Message = msg; Location = None; SuggestedFix = None }

    let info code msg =
        { Rule = RuleCode code; Severity = Severity.Info
          Message = msg; Location = None; SuggestedFix = None }

    let withFix fix finding =
        { finding with SuggestedFix = Some fix }

    let withLocation loc finding =
        { finding with Location = Some loc }

type ValidationResult =
    { Findings: Finding list
      Passed: bool }

module ValidationResult =
    let fromFindings findings =
        { Findings = findings
          Passed = findings |> List.forall (fun f -> f.Severity <> Severity.Error) }

    let empty = { Findings = []; Passed = true }

    let merge a b =
        fromFindings (a.Findings @ b.Findings)

/// A validation rule is a pure function from context + document to findings.
type ValidationContext =
    { Jurisdiction: Jurisdiction
      CourtLevel: CourtLevel
      FilingType: FilingType }

type Rule = ValidationContext -> LegalDocument -> Finding list

module RuleEngine =
    let runRules (rules: Rule list) (ctx: ValidationContext) (doc: LegalDocument) =
        let findings = rules |> List.collect (fun rule -> rule ctx doc)
        ValidationResult.fromFindings findings

    let compose (rules: Rule list) : Rule =
        fun ctx doc -> rules |> List.collect (fun rule -> rule ctx doc)
