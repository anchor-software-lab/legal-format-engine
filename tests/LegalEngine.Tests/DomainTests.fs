module LegalEngine.Tests.DomainTests

open Xunit
open LegalEngine.Domain

[<Fact>]
let ``HeadingLevel toInt roundtrips`` () =
    for level in [ HeadingLevel.Level1; HeadingLevel.Level2; HeadingLevel.Level3; HeadingLevel.Level4 ] do
        let n = HeadingLevel.toInt level
        Assert.Equal(Some level, HeadingLevel.fromInt n)

[<Fact>]
let ``HeadingLevel fromInt returns None for invalid`` () =
    Assert.Equal(None, HeadingLevel.fromInt 0)
    Assert.Equal(None, HeadingLevel.fromInt 5)
    Assert.Equal(None, HeadingLevel.fromInt -1)

[<Fact>]
let ``ContentBlock text creates body text block`` () =
    let block = ContentBlock.text "Hello world"
    Assert.Equal("Hello world", block.Text)
    Assert.True(block.IsBodyText)
    Assert.False(block.IsCaption)
    Assert.False(block.Bold)

[<Fact>]
let ``ContentBlock caption creates caption block`` () =
    let block = ContentBlock.caption "COURT NAME" true Alignment.Center
    Assert.Equal("COURT NAME", block.Text)
    Assert.True(block.Bold)
    Assert.True(block.IsCaption)
    Assert.False(block.IsBodyText)

[<Fact>]
let ``Section create builds correct section`` () =
    let section = Section.create "arg" "Argument" HeadingLevel.Level1 []
    Assert.Equal("arg", section.Id)
    Assert.Equal("Argument", section.HeadingText)
    Assert.Equal(HeadingLevel.Level1, section.HeadingLevel)
    Assert.True(section.Content.IsEmpty)
    Assert.True(section.Subsections.IsEmpty)
    Assert.False(section.IsGenerated)

[<Fact>]
let ``LegalDocument empty has no sections or issues`` () =
    let doc = LegalDocument.empty
    Assert.True(doc.Sections.IsEmpty)
    Assert.True(doc.Issues.IsEmpty)
    Assert.True(doc.Caption.IsNone)
    Assert.True(doc.SignatureBlock.IsNone)

[<Fact>]
let ``Finding constructors set correct severity`` () =
    let err = Finding.error "TEST-001" "Something failed"
    let warn = Finding.warning "TEST-002" "Something might be wrong"
    let inf = Finding.info "TEST-003" "FYI"
    Assert.Equal(Severity.Error, err.Severity)
    Assert.Equal(Severity.Warning, warn.Severity)
    Assert.Equal(Severity.Info, inf.Severity)

[<Fact>]
let ``Finding withFix adds suggested fix`` () =
    let finding = Finding.error "TEST-001" "Missing section"
                  |> Finding.withFix "Add the conclusion section"
    Assert.Equal(Some "Add the conclusion section", finding.SuggestedFix)

[<Fact>]
let ``ValidationResult fromFindings detects errors`` () =
    let findings = [ Finding.error "E1" "Error"; Finding.warning "W1" "Warning" ]
    let result = ValidationResult.fromFindings findings
    Assert.False(result.Passed)
    Assert.Equal(2, result.Findings.Length)

[<Fact>]
let ``ValidationResult fromFindings passes with no errors`` () =
    let findings = [ Finding.warning "W1" "Warning"; Finding.info "I1" "Info" ]
    let result = ValidationResult.fromFindings findings
    Assert.True(result.Passed)

[<Fact>]
let ``ValidationResult merge combines findings`` () =
    let a = ValidationResult.fromFindings [ Finding.warning "W1" "W" ]
    let b = ValidationResult.fromFindings [ Finding.error "E1" "E" ]
    let merged = ValidationResult.merge a b
    Assert.Equal(2, merged.Findings.Length)
    Assert.False(merged.Passed)

[<Fact>]
let ``RuleEngine runRules composes rules`` () =
    let rule1 _ _ = [ Finding.warning "R1" "Rule 1 warning" ]
    let rule2 _ _ = [ Finding.error "R2" "Rule 2 error" ]
    let ctx = { Jurisdiction = Jurisdiction.Wisconsin
                CourtLevel = CourtLevel.Appellate
                FilingType = FilingType.AppellantBrief }
    let result = RuleEngine.runRules [ rule1; rule2 ] ctx LegalDocument.empty
    Assert.False(result.Passed)
    Assert.Equal(2, result.Findings.Length)

[<Fact>]
let ``PageFormat defaults are standard legal`` () =
    let pf = PageFormat.defaults
    Assert.Equal("Times New Roman", pf.FontName)
    Assert.Equal(12.0, pf.FontSizePt)
    Assert.Equal(2.0, pf.LineSpacing)
    Assert.Equal(1.0, pf.MarginTopInches)
    Assert.Equal(0.5, pf.FirstLineIndentInches)

[<Fact>]
let ``CaptionRule defaults use standard values`` () =
    let cr = CaptionRule.defaults
    Assert.Equal("upper", cr.CourtLineStyle)
    Assert.Equal("v.", cr.PartySeparator)
    Assert.True(cr.IncludeDistrict)
