namespace LegalEngine.Domain

/// Core domain types for the legal compliance engine.
/// These discriminated unions model the legal domain with
/// exhaustive pattern matching — impossible states are unrepresentable.

[<RequireQualifiedAccess>]
type Jurisdiction =
    | Wisconsin
    | Illinois
    | California
    | NewYork
    | Texas
    | Ohio
    | Pennsylvania
    | Florida
    | Minnesota
    | Michigan
    | Federal of circuit: string
    | Other of name: string

[<RequireQualifiedAccess>]
type CourtLevel =
    | Trial
    | Appellate
    | Supreme

[<RequireQualifiedAccess>]
type FilingType =
    | AppellantBrief
    | RespondentBrief
    | ReplyBrief
    | Motion
    | Petition
    | Appendix
    | LetterBrief

[<RequireQualifiedAccess>]
type SectionKind =
    | CoverPage
    | TableOfContents
    | TableOfAuthorities
    | StatementOfIssues
    | OralArgumentPosition
    | StatementOfCase
    | StatementOfFacts
    | StatementOfCaseAndFacts
    | Argument
    | Conclusion
    | Certifications
    | SignatureBlock
    | UnknownSection of label: string

[<RequireQualifiedAccess>]
type CaptionPartyRole =
    | Plaintiff
    | Defendant
    | Petitioner
    | Respondent
    | Appellant
    | Appellee
    | Intervenor
    | Amicus

[<RequireQualifiedAccess>]
type Alignment =
    | Left
    | Center
    | Right
    | Justify

[<RequireQualifiedAccess>]
type HeadingLevel =
    | Level1
    | Level2
    | Level3
    | Level4

module HeadingLevel =
    let toInt =
        function
        | HeadingLevel.Level1 -> 1
        | HeadingLevel.Level2 -> 2
        | HeadingLevel.Level3 -> 3
        | HeadingLevel.Level4 -> 4

    let fromInt =
        function
        | 1 -> Some HeadingLevel.Level1
        | 2 -> Some HeadingLevel.Level2
        | 3 -> Some HeadingLevel.Level3
        | 4 -> Some HeadingLevel.Level4
        | _ -> None

[<RequireQualifiedAccess>]
type CaseStyle =
    | Upper
    | Title
    | Sentence

[<RequireQualifiedAccess>]
type NumberingType =
    | Roman
    | AlphaUpper
    | AlphaLower
    | Arabic
