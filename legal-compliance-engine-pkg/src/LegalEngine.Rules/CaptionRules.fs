namespace LegalEngine.Rules

/// Caption generation engine.
/// Generates jurisdiction-specific caption blocks from case metadata
/// and caption formatting rules.

open LegalEngine.Domain

module CaptionRules =

    /// Box-drawing horizontal line character, repeated for a rule line.
    let private horizontalRuleText = System.String('\u2500', 50)

    /// Parse an alignment string to the Alignment DU.
    let private parseAlignment (s: string) : Alignment =
        match s.ToLowerInvariant() with
        | "left" -> Alignment.Left
        | "right" -> Alignment.Right
        | "center" -> Alignment.Center
        | "justify" -> Alignment.Justify
        | _ -> Alignment.Center

    /// Create a caption content block.
    let private captionLine
        (text: string)
        (bold: bool)
        (italic: bool)
        (underline: bool)
        (alignment: Alignment)
        : ContentBlock =
        { Text = text
          Bold = bold
          Italic = italic
          Underline = underline
          Alignment = alignment
          IsBodyText = false
          IsCaption = true
          IndentInches = 0.0 }

    let private simpleCaptionLine text alignment =
        captionLine text false false false alignment

    let private boldCaptionLine text alignment =
        captionLine text true false false alignment

    let private italicCaptionLine text alignment =
        captionLine text false true false alignment

    let private blankLine () =
        simpleCaptionLine "" Alignment.Center

    let private horizontalRule () =
        simpleCaptionLine horizontalRuleText Alignment.Center

    /// Apply case style to text.
    let private applyStyle (style: string) (text: string) =
        match style.ToLowerInvariant() with
        | "upper" -> text.ToUpperInvariant()
        | "title" ->
            let ti = System.Globalization.CultureInfo.InvariantCulture.TextInfo
            ti.ToTitleCase(text.ToLowerInvariant())
        | "sentence" ->
            if System.String.IsNullOrWhiteSpace text then text
            else
                let lower = text.ToLowerInvariant()
                string (System.Char.ToUpperInvariant(lower.[0])) + lower.[1..]
        | _ -> text

    /// Format a party role enum to a display label.
    let private formatRoleLabel (role: CaptionPartyRole) : string =
        match role with
        | CaptionPartyRole.Plaintiff -> "Plaintiff"
        | CaptionPartyRole.Defendant -> "Defendant"
        | CaptionPartyRole.Petitioner -> "Petitioner"
        | CaptionPartyRole.Respondent -> "Respondent"
        | CaptionPartyRole.Appellant -> "Appellant"
        | CaptionPartyRole.Appellee -> "Appellee"
        | CaptionPartyRole.Intervenor -> "Intervenor"
        | CaptionPartyRole.Amicus -> "Amicus Curiae"

    /// Add party lines with separator to the caption.
    let private addPartyLines (metadata: DocumentMetadata) (rule: CaptionRule) : ContentBlock list =
        let parties = metadata.Case.Parties
        if List.isEmpty parties then []
        else
            let partyAlign = parseAlignment rule.PartyAlignment
            let lines = System.Collections.Generic.List<ContentBlock>()

            let addParty (party: Party) =
                let name =
                    if rule.PartyNameStyle = "upper" then party.Name.ToUpperInvariant()
                    else party.Name
                lines.Add(boldCaptionLine (name + ",") partyAlign)

                let roleText =
                    let designation =
                        match party.Designation with
                        | Some d -> d
                        | None -> formatRoleLabel party.Role
                    if rule.PartyRoleStyle = "title" then
                        let ti = System.Globalization.CultureInfo.InvariantCulture.TextInfo
                        ti.ToTitleCase(designation.ToLowerInvariant())
                    else designation

                if rule.PartyRoleIndented then
                    lines.Add(italicCaptionLine (roleText + ".") partyAlign)
                else
                    lines.Add(simpleCaptionLine (roleText + ".") partyAlign)

            // First party
            lines.Add(blankLine ())
            addParty parties.[0]

            // Separator
            lines.Add(blankLine ())
            lines.Add(simpleCaptionLine rule.PartySeparator partyAlign)
            lines.Add(blankLine ())

            // Second party
            if parties.Length > 1 then
                addParty parties.[1]

            // Additional parties
            for party in (if parties.Length > 2 then parties.[2..] else []) do
                lines.Add(blankLine ())
                addParty party

            lines |> Seq.toList

    /// Generate a formatted caption block from metadata and rules.
    /// Creates court name line, party block with separator, case number,
    /// appeal-from line, and document title with horizontal rules.
    let generateCaption (metadata: DocumentMetadata) (rule: CaptionRule) : CaptionBlock =
        let lines = System.Collections.Generic.List<ContentBlock>()
        let courtAlign = parseAlignment rule.CourtLineAlignment

        // Court name line
        let courtName = applyStyle rule.CourtLineStyle metadata.Case.CourtName
        lines.Add(boldCaptionLine courtName courtAlign)

        // District line
        if rule.IncludeDistrict then
            match metadata.Case.District with
            | Some district ->
                lines.Add(blankLine ())
                lines.Add(boldCaptionLine (district.ToUpperInvariant()) courtAlign)
            | None -> ()

        // Blank spacer
        lines.Add(blankLine ())

        // Case number
        let prefix = if System.String.IsNullOrWhiteSpace rule.CaseNumberPrefix then "Case No." else rule.CaseNumberPrefix
        let caseNumAlign = parseAlignment rule.CaseNumberAlignment
        lines.Add(boldCaptionLine (sprintf "%s %s" prefix metadata.Case.CaseNumber) caseNumAlign)

        // Horizontal rule before parties
        lines.Add(blankLine ())
        lines.Add(horizontalRule ())

        // Party block
        let partyLines = addPartyLines metadata rule
        for line in partyLines do
            lines.Add(line)

        // Horizontal rule after parties
        lines.Add(blankLine ())
        lines.Add(horizontalRule ())

        // Appeal from line
        if rule.IncludeAppealFrom then
            match metadata.Case.CountyOfOrigin with
            | Some county ->
                let appealAlign = parseAlignment rule.AppealFromAlignment
                lines.Add(blankLine ())
                lines.Add(italicCaptionLine "On an Appeal from a Judgment of Conviction," appealAlign)
                let appealLoc =
                    let baseLoc = sprintf "Entered in the %s Circuit Court" county
                    match metadata.Case.JudgeName with
                    | Some judge -> sprintf "%s, the\nHonorable %s, Presiding" baseLoc judge
                    | None -> baseLoc
                lines.Add(italicCaptionLine appealLoc appealAlign)
                lines.Add(blankLine ())
                lines.Add(horizontalRule ())
            | None -> ()

        // Document title
        lines.Add(blankLine ())
        let docTitle = applyStyle rule.DocumentTitleStyle metadata.DocumentTitle
        let titleAlign = parseAlignment rule.DocumentTitleAlignment
        let titleWords = docTitle.Split(' ')
        if titleWords.Length > 3 then
            let mid = titleWords.Length / 2
            let line1 = titleWords.[..mid-1] |> String.concat " "
            let line2 = titleWords.[mid..] |> String.concat " "
            lines.Add(boldCaptionLine line1 titleAlign)
            lines.Add(boldCaptionLine line2 titleAlign)
        else
            lines.Add(boldCaptionLine docTitle titleAlign)

        // Horizontal rule after title
        lines.Add(blankLine ())
        lines.Add(horizontalRule ())

        { Lines = lines |> Seq.toList }
