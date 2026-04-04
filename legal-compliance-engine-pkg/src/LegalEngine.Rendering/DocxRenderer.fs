namespace LegalEngine.Rendering

open System
open System.IO
open DocumentFormat.OpenXml
open DocumentFormat.OpenXml.Packaging
open DocumentFormat.OpenXml.Wordprocessing
open LegalEngine.Domain

/// DOCX renderer for legal documents.
/// Produces properly formatted Word documents from the internal
/// LegalDocument representation using DocumentFormat.OpenXml.
module DocxRenderer =

    // ── Conversion helpers ──────────────────────────────────────────

    /// Convert inches to EMUs (English Metric Units). 1 inch = 914400 EMUs.
    let private inchesToEmu (inches: float) : int64 =
        int64 (inches * 914400.0)

    /// Convert inches to twentieths of a point (twips). 1 inch = 1440 twips.
    let private inchesToTwips (inches: float) : int =
        int (inches * 1440.0)

    /// Convert points to half-points. OpenXml font sizes are in half-points.
    let private ptToHalfPoints (pt: float) : string =
        string (int (pt * 2.0))

    /// Convert points to twentieths of a point.
    let private ptToTwips (pt: float) : string =
        string (int (pt * 20.0))

    // ── Alignment mapping ───────────────────────────────────────────

    let private toJustification (alignment: Alignment) : JustificationValues =
        match alignment with
        | Alignment.Left -> JustificationValues.Left
        | Alignment.Center -> JustificationValues.Center
        | Alignment.Right -> JustificationValues.Right
        | Alignment.Justify -> JustificationValues.Both

    let private alignmentFromString (s: string) : JustificationValues =
        match s.ToLowerInvariant() with
        | "left" -> JustificationValues.Left
        | "center" | "centre" -> JustificationValues.Center
        | "right" -> JustificationValues.Right
        | "justify" | "both" -> JustificationValues.Both
        | _ -> JustificationValues.Both

    // ── Page setup ──────────────────────────────────────────────────

    let private setupPage (body: Body) (fmt: PageFormat) =
        let sectPr = SectionProperties()
        let pgSz = PageSize()
        pgSz.Width <- UInt32Value(uint32 (inchesToTwips fmt.PageWidthInches))
        pgSz.Height <- UInt32Value(uint32 (inchesToTwips fmt.PageHeightInches))
        pgSz.Orient <- EnumValue(PageOrientationValues.Portrait)
        sectPr.AppendChild(pgSz) |> ignore

        let pgMar = PageMargin()
        pgMar.Top <- Int32Value(int32 (inchesToTwips fmt.MarginTopInches))
        pgMar.Bottom <- Int32Value(int32 (inchesToTwips fmt.MarginBottomInches))
        pgMar.Left <- UInt32Value(uint32 (inchesToTwips fmt.MarginLeftInches))
        pgMar.Right <- UInt32Value(uint32 (inchesToTwips fmt.MarginRightInches))
        sectPr.AppendChild(pgMar) |> ignore

        body.AppendChild(sectPr) |> ignore

    // ── Default font via style ──────────────────────────────────────

    let private setDefaultFont (stylesPart: StyleDefinitionsPart) (fmt: PageFormat) =
        let styles = Styles()

        // Default run properties
        let docDefaults = DocDefaults()
        let runPrDefault = RunPropertiesDefault()
        let rPr = RunPropertiesBaseStyle()
        let runFonts = RunFonts()
        runFonts.Ascii <- StringValue(fmt.FontName)
        runFonts.HighAnsi <- StringValue(fmt.FontName)
        rPr.AppendChild(runFonts) |> ignore
        let fontSize = FontSize()
        fontSize.Val <- StringValue(ptToHalfPoints fmt.FontSizePt)
        rPr.AppendChild(fontSize) |> ignore
        runPrDefault.RunPropertiesBaseStyle <- rPr
        docDefaults.RunPropertiesDefault <- runPrDefault

        // Default paragraph properties
        let parPrDefault = ParagraphPropertiesDefault()
        let pPr = ParagraphPropertiesBaseStyle()
        let spacing = SpacingBetweenLines()
        // Double spacing: 480 twips (24pt line = 2x 12pt)
        spacing.Line <- StringValue(string (int (fmt.LineSpacing * 240.0)))
        spacing.LineRule <- EnumValue(LineSpacingRuleValues.Auto)
        spacing.Before <- StringValue("0")
        spacing.After <- StringValue("0")
        pPr.AppendChild(spacing) |> ignore
        parPrDefault.ParagraphPropertiesBaseStyle <- pPr
        docDefaults.ParagraphPropertiesDefault <- parPrDefault

        styles.AppendChild(docDefaults) |> ignore
        stylesPart.Styles <- styles

    // ── Hyphenation ─────────────────────────────────────────────────

    let private enableHyphenation (settingsPart: DocumentSettingsPart) =
        let settings = Settings()
        let autoHyphen = AutoHyphenation()
        autoHyphen.Val <- OnOffValue(true)
        settings.AppendChild(autoHyphen) |> ignore
        settingsPart.Settings <- settings

    // ── Run creation ────────────────────────────────────────────────

    let private makeRun (text: string) (fmt: PageFormat) (bold: bool) (italic: bool) (underline: bool) : Run =
        let run = Run()
        let rPr = RunProperties()

        let runFonts = RunFonts()
        runFonts.Ascii <- StringValue(fmt.FontName)
        runFonts.HighAnsi <- StringValue(fmt.FontName)
        rPr.AppendChild(runFonts) |> ignore

        let fontSize = FontSize()
        fontSize.Val <- StringValue(ptToHalfPoints fmt.FontSizePt)
        rPr.AppendChild(fontSize) |> ignore

        if bold then
            rPr.AppendChild(Bold()) |> ignore
        if italic then
            rPr.AppendChild(Italic()) |> ignore
        if underline then
            let u = Underline()
            u.Val <- EnumValue(UnderlineValues.Single)
            rPr.AppendChild(u) |> ignore

        run.RunProperties <- rPr
        let t = Text(text)
        t.Space <- EnumValue(SpaceProcessingModeValues.Preserve)
        run.AppendChild(t) |> ignore
        run

    // ── Paragraph creation helpers ──────────────────────────────────

    let private makeParagraph
        (text: string)
        (fmt: PageFormat)
        (justification: JustificationValues)
        (lineSpacingTwips: int)
        (firstLineIndentTwips: int)
        (leftIndentTwips: int)
        (bold: bool)
        (italic: bool)
        (underline: bool)
        (spaceAfterPt: float) : Paragraph =

        let para = Paragraph()
        let pPr = ParagraphProperties()
        let jc = Justification()
        jc.Val <- EnumValue(justification)
        pPr.AppendChild(jc) |> ignore

        let spacing = SpacingBetweenLines()
        spacing.Line <- StringValue(string lineSpacingTwips)
        spacing.LineRule <- EnumValue(LineSpacingRuleValues.Auto)
        spacing.Before <- StringValue("0")
        spacing.After <- StringValue(ptToTwips spaceAfterPt)
        pPr.AppendChild(spacing) |> ignore

        if firstLineIndentTwips > 0 || leftIndentTwips > 0 then
            let ind = Indentation()
            if firstLineIndentTwips > 0 then
                ind.FirstLine <- StringValue(string firstLineIndentTwips)
            if leftIndentTwips > 0 then
                ind.Left <- StringValue(string leftIndentTwips)
            pPr.AppendChild(ind) |> ignore

        para.ParagraphProperties <- pPr
        let run = makeRun text fmt bold italic underline
        para.AppendChild(run) |> ignore
        para

    // ── Caption rendering ───────────────────────────────────────────

    let private renderCaption (body: Body) (caption: CaptionBlock) (fmt: PageFormat) =
        for line in caption.Lines do
            let justification = toJustification line.Alignment
            // Single spacing = 240 twips
            let para =
                makeParagraph
                    line.Text fmt justification
                    240 0 0
                    line.Bold line.Italic line.Underline
                    2.0
            body.AppendChild(para) |> ignore

    // ── Page break ──────────────────────────────────────────────────

    let private addPageBreak (body: Body) =
        let para = Paragraph()
        let run = Run()
        let br = Break()
        br.Type <- EnumValue(BreakValues.Page)
        run.AppendChild(br) |> ignore
        para.AppendChild(run) |> ignore
        body.AppendChild(para) |> ignore

    // ── Section rendering ───────────────────────────────────────────

    let private renderHeading (body: Body) (text: string) (fmt: PageFormat) (ruleset: Ruleset) (level: HeadingLevel) (numberingPrefix: string option) =
        let headingRule = Ruleset.getHeadingRule (HeadingLevel.toInt level) ruleset
        let bold =
            match headingRule with
            | Some r -> r.Bold
            | None -> true

        let fullText =
            match numberingPrefix with
            | Some prefix -> prefix + " " + text
            | None -> text

        let justification =
            match headingRule with
            | Some r -> alignmentFromString r.Alignment
            | None -> JustificationValues.Center

        let leftIndentTwips =
            match headingRule with
            | Some r -> inchesToTwips r.IndentInches
            | None -> 0

        // Double spacing = 480 twips; headings never have first-line indent
        let para =
            makeParagraph
                fullText fmt justification
                480 0 leftIndentTwips
                bold false false
                0.0
        body.AppendChild(para) |> ignore

    let private renderContentBlock (body: Body) (block: ContentBlock) (fmt: PageFormat) =
        let justification = toJustification block.Alignment

        let lineSpacing, spaceAfter, firstLineIndent =
            if block.IsCaption then
                // Caption: single-spaced, no indent
                240, 2.0, 0
            elif block.IsBodyText then
                // Body: double-spaced, first-line indent, justified
                480, 0.0, inchesToTwips fmt.FirstLineIndentInches
            else
                // Default: double-spaced, no indent
                480, 0.0, 0

        let leftIndentTwips =
            if block.IndentInches > 0.0 then inchesToTwips block.IndentInches
            else 0

        let para =
            makeParagraph
                block.Text fmt justification
                lineSpacing firstLineIndent leftIndentTwips
                block.Bold block.Italic block.Underline
                spaceAfter
        body.AppendChild(para) |> ignore

    let rec private renderSection (body: Body) (section: Section) (fmt: PageFormat) (ruleset: Ruleset) =
        if not (String.IsNullOrWhiteSpace section.HeadingText) then
            renderHeading body section.HeadingText fmt ruleset section.HeadingLevel section.NumberingPrefix

        for block in section.Content do
            renderContentBlock body block fmt

        for sub in section.Subsections do
            renderSection body sub fmt ruleset

    // ── Blank line ──────────────────────────────────────────────────

    let private addBlankLine (body: Body) (fmt: PageFormat) =
        let para = makeParagraph "" fmt JustificationValues.Left 480 0 0 false false false 0.0
        body.AppendChild(para) |> ignore

    // ── Signature block ─────────────────────────────────────────────

    let private renderSignatureBlock (body: Body) (sig': SignatureBlockInfo) (fmt: PageFormat) =
        let lines = [
            "Respectfully submitted,"
            ""
            "____________________________"
            sig'.AttorneyName
            sprintf "State Bar No. %s" sig'.BarNumber
        ]
        let lines =
            match sig'.Firm with
            | Some firm -> lines @ [ firm ]
            | None -> lines
        let lines =
            lines @ [
                sig'.Address
                sprintf "Phone: %s" sig'.Phone
                sprintf "Email: %s" sig'.Email
            ]

        for text in lines do
            let para =
                makeParagraph
                    text fmt JustificationValues.Left
                    480 0 0
                    false false false
                    0.0
            body.AppendChild(para) |> ignore

    // ── Public API ──────────────────────────────────────────────────

    /// Render a LegalDocument to a DOCX file at the specified output path.
    let renderDocx (doc: LegalDocument) (ruleset: Ruleset) (outputPath: string) : unit =
        use wordDoc = WordprocessingDocument.Create(outputPath, WordprocessingDocumentType.Document)

        let mainPart = wordDoc.AddMainDocumentPart()
        let document = Document()
        let body = Body()

        // Set up styles (default font, spacing)
        let stylesPart = mainPart.AddNewPart<StyleDefinitionsPart>()
        setDefaultFont stylesPart ruleset.PageFormat

        // Enable hyphenation
        let settingsPart = mainPart.AddNewPart<DocumentSettingsPart>()
        enableHyphenation settingsPart

        // Render caption
        match doc.Caption with
        | Some caption ->
            renderCaption body caption ruleset.PageFormat
            addPageBreak body
        | None -> ()

        // Render sections
        for section in doc.Sections do
            renderSection body section ruleset.PageFormat ruleset

        // Render signature block
        match doc.SignatureBlock with
        | Some sig' ->
            addBlankLine body ruleset.PageFormat
            renderSignatureBlock body sig' ruleset.PageFormat
        | None -> ()

        // Render certifications with page breaks between
        for cert in doc.Certifications do
            addPageBreak body
            renderSection body cert ruleset.PageFormat ruleset

        // Set up page format (margins, page size) via section properties
        setupPage body ruleset.PageFormat

        document.AppendChild(body) |> ignore
        mainPart.Document <- document
