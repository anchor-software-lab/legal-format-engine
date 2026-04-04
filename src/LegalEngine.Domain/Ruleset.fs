namespace LegalEngine.Domain

/// Typed representation of jurisdiction-specific formatting rules.
/// Loaded from YAML files, never modified at runtime.

type PageFormat =
    { FontName: string
      FontSizePt: float
      LineSpacing: float
      MarginTopInches: float
      MarginBottomInches: float
      MarginLeftInches: float
      MarginRightInches: float
      PageWidthInches: float
      PageHeightInches: float
      FirstLineIndentInches: float
      BodyAlignment: string }

module PageFormat =
    let defaults =
        { FontName = "Times New Roman"
          FontSizePt = 12.0
          LineSpacing = 2.0
          MarginTopInches = 1.0
          MarginBottomInches = 1.0
          MarginLeftInches = 1.0
          MarginRightInches = 1.0
          PageWidthInches = 8.5
          PageHeightInches = 11.0
          FirstLineIndentInches = 0.5
          BodyAlignment = "justify" }

type HeadingRule =
    { Level: int
      CaseStyle: string
      Alignment: string
      Numbering: string option
      Bold: bool
      IndentInches: float }

type RequiredSection =
    { Id: string
      CanonicalName: string
      Aliases: string list
      Order: int
      Required: bool
      HeadingLevel: int
      Subsections: RequiredSection list
      Group: string option }

type CaptionRule =
    { CourtLineStyle: string
      CourtLineAlignment: string
      CaseNumberAlignment: string
      CaseNumberPrefix: string
      PartySeparator: string
      PartyNameStyle: string
      PartyRoleStyle: string
      PartyAlignment: string
      PartyRoleIndented: bool
      DocumentTitleStyle: string
      DocumentTitleAlignment: string
      IncludeDistrict: bool
      IncludeAppealFrom: bool
      AppealFromStyle: string
      AppealFromAlignment: string }

module CaptionRule =
    let defaults =
        { CourtLineStyle = "upper"
          CourtLineAlignment = "center"
          CaseNumberAlignment = "right"
          CaseNumberPrefix = "Case No."
          PartySeparator = "v."
          PartyNameStyle = "upper"
          PartyRoleStyle = "title"
          PartyAlignment = "center"
          PartyRoleIndented = false
          DocumentTitleStyle = "upper"
          DocumentTitleAlignment = "center"
          IncludeDistrict = true
          IncludeAppealFrom = true
          AppealFromStyle = "sentence"
          AppealFromAlignment = "center" }

type CertificationRule =
    { Id: string
      Title: string option
      Template: string }

type SignatureBlockRule =
    { Template: string }

type Ruleset =
    { Jurisdiction: string
      CourtLevel: string
      DocumentType: string
      PageFormat: PageFormat
      HeadingRules: HeadingRule list
      RequiredSections: RequiredSection list
      CaptionRule: CaptionRule
      Certifications: CertificationRule list
      SignatureBlock: SignatureBlockRule option
      SignatureBlockRequired: bool }

module Ruleset =
    let getHeadingRule level (ruleset: Ruleset) =
        ruleset.HeadingRules |> List.tryFind (fun r -> r.Level = level)
