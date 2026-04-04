namespace LegalEngine.Ingestion

open System
open System.IO
open System.Collections.Generic
open DocumentFormat.OpenXml.Packaging
open DocumentFormat.OpenXml.Wordprocessing
open LegalEngine.Domain
open LegalEngine.Parsing

/// DOCX file reader that parses Word documents into LegalDocument.
module DocxReader =

    /// Extract text content from a paragraph element.
    let private paragraphText (para: Paragraph) : string =
        para.InnerText

    /// Check if a paragraph has bold formatting.
    let private isBold (para: Paragraph) : bool =
        let rPr = para.Descendants<RunProperties>() |> Seq.tryHead
        match rPr with
        | Some props -> props.Bold <> null
        | None -> false

    /// Check if a paragraph has italic formatting.
    let private isItalic (para: Paragraph) : bool =
        let rPr = para.Descendants<RunProperties>() |> Seq.tryHead
        match rPr with
        | Some props -> props.Italic <> null
        | None -> false

    /// Check if a paragraph has underline formatting.
    let private isUnderline (para: Paragraph) : bool =
        let rPr = para.Descendants<RunProperties>() |> Seq.tryHead
        match rPr with
        | Some props -> props.Underline <> null && props.Underline.Val <> null
        | None -> false

    /// Get alignment from paragraph properties.
    let private getAlignment (para: Paragraph) : Alignment =
        let pPr = para.ParagraphProperties
        if pPr <> null && pPr.Justification <> null && pPr.Justification.Val <> null then
            let justVal = pPr.Justification.Val.Value
            if justVal = JustificationValues.Center then Alignment.Center
            elif justVal = JustificationValues.Right then Alignment.Right
            elif justVal = JustificationValues.Both then Alignment.Justify
            else Alignment.Left
        else
            Alignment.Left

    /// Get indent in inches from paragraph properties.
    let private getIndentInches (para: Paragraph) : float =
        let pPr = para.ParagraphProperties
        if pPr <> null && pPr.Indentation <> null then
            let indent = pPr.Indentation
            if indent.Left <> null then
                // OOXML uses twips (1/1440 inch) for indentation
                match Int32.TryParse(indent.Left.Value) with
                | true, twips -> float twips / 1440.0
                | _ -> 0.0
            elif indent.Start <> null then
                match Int32.TryParse(indent.Start.Value) with
                | true, twips -> float twips / 1440.0
                | _ -> 0.0
            else
                0.0
        else
            0.0

    /// Convert a paragraph to a ContentBlock.
    let private toContentBlock (para: Paragraph) : ContentBlock =
        { Text = paragraphText para
          Bold = isBold para
          Italic = isItalic para
          Underline = isUnderline para
          Alignment = getAlignment para
          IsBodyText = true
          IsCaption = false
          IndentInches = getIndentInches para }

    /// Parse a DOCX file into a LegalDocument.
    let parseDocx (filePath: string) : LegalDocument =
        if not (File.Exists(filePath)) then
            invalidArg "filePath" (sprintf "File not found: '%s'" filePath)

        use doc = WordprocessingDocument.Open(filePath, false)
        let body = doc.MainDocumentPart.Document.Body

        let paragraphs =
            body.Elements<Paragraph>()
            |> Seq.toList

        // Convert paragraphs to content blocks
        let blocks =
            paragraphs
            |> List.map toContentBlock

        // Extract raw text for further processing
        let rawText =
            blocks
            |> List.map (fun b -> b.Text)
            |> String.concat "\n"

        // Use the plain text heading detection on the raw text to build sections
        let lines = blocks |> List.map (fun b -> b.Text)
        let classified = LegalEngine.Parsing.SectionBuilder.classifyLines lines
        let sections = LegalEngine.Parsing.SectionBuilder.buildSections classified

        { LegalDocument.empty with
            Sections = sections
            RawText = Some rawText }

    /// Extract format profile details from a DOCX file.
    /// Returns a dictionary of formatting properties found in the document.
    let extractFormatProfile (filePath: string) : Dictionary<string, string> =
        if not (File.Exists(filePath)) then
            invalidArg "filePath" (sprintf "File not found: '%s'" filePath)

        let profile = Dictionary<string, string>()

        use doc = WordprocessingDocument.Open(filePath, false)
        let body = doc.MainDocumentPart.Document.Body

        // Extract page/section properties
        let sectionProps = body.Elements<SectionProperties>() |> Seq.tryHead
        match sectionProps with
        | Some sp ->
            let pageSize = sp.Elements<PageSize>() |> Seq.tryHead
            match pageSize with
            | Some ps ->
                if ps.Width <> null then
                    profile.["PageWidth"] <- ps.Width.Value.ToString()
                if ps.Height <> null then
                    profile.["PageHeight"] <- ps.Height.Value.ToString()
            | None -> ()

            let pageMargin = sp.Elements<PageMargin>() |> Seq.tryHead
            match pageMargin with
            | Some pm ->
                if pm.Top <> null then
                    profile.["MarginTop"] <- pm.Top.Value.ToString()
                if pm.Bottom <> null then
                    profile.["MarginBottom"] <- pm.Bottom.Value.ToString()
                if pm.Left <> null then
                    profile.["MarginLeft"] <- pm.Left.Value.ToString()
                if pm.Right <> null then
                    profile.["MarginRight"] <- pm.Right.Value.ToString()
            | None -> ()
        | None -> ()

        // Extract default font info from first paragraph with runs
        let firstRunProps =
            body.Descendants<RunProperties>() |> Seq.tryHead
        match firstRunProps with
        | Some rp ->
            if rp.RunFonts <> null && rp.RunFonts.Ascii <> null then
                profile.["FontName"] <- rp.RunFonts.Ascii.Value
            if rp.FontSize <> null then
                profile.["FontSize"] <- rp.FontSize.Val.Value
        | None -> ()

        profile
