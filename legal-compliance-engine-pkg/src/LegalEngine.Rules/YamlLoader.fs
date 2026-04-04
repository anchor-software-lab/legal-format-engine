namespace LegalEngine.Rules

/// Load and validate ruleset YAML files.
/// Looks up: rulesets/{jurisdiction}/{variant}_{courtLevel}_{documentType}.yaml
/// Falls back to: rulesets/{jurisdiction}/{courtLevel}_{documentType}.yaml

open System
open System.IO
open YamlDotNet.Serialization
open YamlDotNet.Serialization.NamingConventions
open LegalEngine.Domain

// ---------- Internal YAML DTOs (snake_case property names matching YAML) ----------

/// YamlDotNet deserialization targets. These mirror the YAML schema
/// with mutable properties and nullable types, then get mapped to
/// the immutable Domain.Ruleset records.

[<CLIMutable>]
type YamlPageFormat =
    { font_name: string
      font_size_pt: float
      line_spacing: float
      margin_top_inches: float
      margin_bottom_inches: float
      margin_left_inches: float
      margin_right_inches: float
      page_width_inches: float
      page_height_inches: float
      first_line_indent_inches: float
      body_alignment: string }

[<CLIMutable>]
type YamlHeadingRule =
    { level: int
      case_style: string
      alignment: string
      numbering: string
      bold: bool
      indent_inches: float }

[<CLIMutable>]
type YamlRequiredSection =
    { id: string
      canonical_name: string
      aliases: System.Collections.Generic.List<string>
      order: int
      required: bool
      heading_level: int
      subsections: System.Collections.Generic.List<YamlRequiredSection>
      group: string }

[<CLIMutable>]
type YamlCaptionRule =
    { court_line_style: string
      court_line_alignment: string
      case_number_alignment: string
      case_number_prefix: string
      party_separator: string
      party_name_style: string
      party_role_style: string
      party_alignment: string
      party_role_indented: bool
      document_title_style: string
      document_title_alignment: string
      include_district: bool
      include_appeal_from: bool
      appeal_from_style: string
      appeal_from_alignment: string }

[<CLIMutable>]
type YamlCertificationRule =
    { id: string
      title: string
      template: string }

[<CLIMutable>]
type YamlSignatureBlock =
    { template: string }

[<CLIMutable>]
type YamlRuleset =
    { jurisdiction: string
      court_level: string
      document_type: string
      page_format: YamlPageFormat
      heading_rules: System.Collections.Generic.List<YamlHeadingRule>
      required_sections: System.Collections.Generic.List<YamlRequiredSection>
      caption_rule: YamlCaptionRule
      certifications: System.Collections.Generic.List<YamlCertificationRule>
      signature_block: YamlSignatureBlock
      signature_block_required: bool }

// ---------- Mapping from YAML DTOs to Domain types ----------

module internal YamlMapping =

    let private toOption (s: string) =
        if String.IsNullOrWhiteSpace s then None else Some s

    let private listOfGeneric (lst: System.Collections.Generic.List<'a>) : 'a list =
        if isNull (box lst) then [] else lst |> Seq.toList

    let mapPageFormat (y: YamlPageFormat) : PageFormat =
        if isNull (box y) then
            PageFormat.defaults
        else
            { FontName = if isNull y.font_name then "Times New Roman" else y.font_name
              FontSizePt = if y.font_size_pt = 0.0 then 12.0 else y.font_size_pt
              LineSpacing = if y.line_spacing = 0.0 then 2.0 else y.line_spacing
              MarginTopInches = if y.margin_top_inches = 0.0 then 1.0 else y.margin_top_inches
              MarginBottomInches = if y.margin_bottom_inches = 0.0 then 1.0 else y.margin_bottom_inches
              MarginLeftInches = if y.margin_left_inches = 0.0 then 1.0 else y.margin_left_inches
              MarginRightInches = if y.margin_right_inches = 0.0 then 1.0 else y.margin_right_inches
              PageWidthInches = if y.page_width_inches = 0.0 then 8.5 else y.page_width_inches
              PageHeightInches = if y.page_height_inches = 0.0 then 11.0 else y.page_height_inches
              FirstLineIndentInches = y.first_line_indent_inches
              BodyAlignment = if isNull y.body_alignment then "justify" else y.body_alignment }

    let mapHeadingRule (y: YamlHeadingRule) : HeadingRule =
        { Level = y.level
          CaseStyle = if isNull y.case_style then "title" else y.case_style
          Alignment = if isNull y.alignment then "left" else y.alignment
          Numbering = toOption y.numbering
          Bold = y.bold
          IndentInches = y.indent_inches }

    let rec mapRequiredSection (y: YamlRequiredSection) : RequiredSection =
        { Id = if isNull y.id then "" else y.id
          CanonicalName = if isNull y.canonical_name then "" else y.canonical_name
          Aliases = listOfGeneric y.aliases
          Order = y.order
          Required = y.required
          HeadingLevel = if y.heading_level = 0 then 1 else y.heading_level
          Subsections = listOfGeneric y.subsections |> List.map mapRequiredSection
          Group = toOption y.group }

    let mapCaptionRule (y: YamlCaptionRule) : CaptionRule =
        if isNull (box y) then
            CaptionRule.defaults
        else
            { CourtLineStyle = if isNull y.court_line_style then "upper" else y.court_line_style
              CourtLineAlignment = if isNull y.court_line_alignment then "center" else y.court_line_alignment
              CaseNumberAlignment = if isNull y.case_number_alignment then "right" else y.case_number_alignment
              CaseNumberPrefix = if isNull y.case_number_prefix then "Case No." else y.case_number_prefix
              PartySeparator = if isNull y.party_separator then "v." else y.party_separator
              PartyNameStyle = if isNull y.party_name_style then "upper" else y.party_name_style
              PartyRoleStyle = if isNull y.party_role_style then "title" else y.party_role_style
              PartyAlignment = if isNull y.party_alignment then "center" else y.party_alignment
              PartyRoleIndented = y.party_role_indented
              DocumentTitleStyle = if isNull y.document_title_style then "upper" else y.document_title_style
              DocumentTitleAlignment = if isNull y.document_title_alignment then "center" else y.document_title_alignment
              IncludeDistrict = y.include_district
              IncludeAppealFrom = y.include_appeal_from
              AppealFromStyle = if isNull y.appeal_from_style then "sentence" else y.appeal_from_style
              AppealFromAlignment = if isNull y.appeal_from_alignment then "center" else y.appeal_from_alignment }

    let mapCertificationRule (y: YamlCertificationRule) : CertificationRule =
        { Id = if isNull y.id then "" else y.id
          Title = toOption y.title
          Template = if isNull y.template then "" else y.template }

    let mapSignatureBlock (y: YamlSignatureBlock) : SignatureBlockRule option =
        if isNull (box y) || isNull y.template then
            None
        else
            Some { Template = y.template }

    let mapRuleset (y: YamlRuleset) : Ruleset =
        { Jurisdiction = if isNull y.jurisdiction then "" else y.jurisdiction
          CourtLevel = if isNull y.court_level then "" else y.court_level
          DocumentType = if isNull y.document_type then "" else y.document_type
          PageFormat = mapPageFormat y.page_format
          HeadingRules = listOfGeneric y.heading_rules |> List.map mapHeadingRule
          RequiredSections = listOfGeneric y.required_sections |> List.map mapRequiredSection
          CaptionRule = mapCaptionRule y.caption_rule
          Certifications = listOfGeneric y.certifications |> List.map mapCertificationRule
          SignatureBlock = mapSignatureBlock y.signature_block
          SignatureBlockRequired = y.signature_block_required }

// ---------- Public API ----------

module YamlLoader =

    /// Default directory for bundled rulesets, relative to the assembly location.
    let mutable RulesetsDirectory =
        let asmDir =
            Path.GetDirectoryName(
                System.Reflection.Assembly.GetExecutingAssembly().Location)
        Path.Combine(asmDir, "rulesets")

    let private buildDeserializer () =
        DeserializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .IgnoreUnmatchedProperties()
            .Build()

    /// Load a ruleset from YAML text.
    let loadFromYaml (yamlText: string) : Ruleset =
        let deserializer = buildDeserializer ()
        let dto = deserializer.Deserialize<YamlRuleset>(yamlText)
        if isNull (box dto) then
            failwith "Ruleset file must contain a YAML mapping"
        YamlMapping.mapRuleset dto

    /// Load a ruleset from a file path.
    let loadFromFile (path: string) : Ruleset =
        if not (File.Exists path) then
            failwithf "Ruleset file not found: %s" path
        let yamlText = File.ReadAllText(path, Text.Encoding.UTF8)
        loadFromYaml yamlText

    /// Load a ruleset by jurisdiction/courtLevel/documentType lookup.
    /// Searches RulesetsDirectory for matching YAML files.
    /// Tries variant-specific file first, then falls back to generic.
    let loadRuleset
        (jurisdiction: string)
        (courtLevel: string)
        (documentType: string)
        (variant: string option)
        : Ruleset =

        let filenames =
            match variant with
            | Some v ->
                [ sprintf "%s_%s_%s.yaml" v courtLevel documentType
                  sprintf "%s_%s.yaml" courtLevel documentType ]
            | None ->
                [ sprintf "%s_%s.yaml" courtLevel documentType ]

        let found =
            filenames
            |> List.tryPick (fun filename ->
                let fullPath = Path.Combine(RulesetsDirectory, jurisdiction, filename)
                if File.Exists fullPath then Some fullPath else None)

        match found with
        | Some path -> loadFromFile path
        | None ->
            let variantLabel =
                match variant with
                | Some v -> sprintf " (variant: %s)" v
                | None -> ""
            failwithf
                "No ruleset found for %s/%s_%s%s. Tried: %A"
                jurisdiction courtLevel documentType variantLabel filenames
