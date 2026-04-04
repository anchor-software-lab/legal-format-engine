namespace LegalEngine.Rendering

open System.Text
open LegalEngine.Domain

/// Markdown renderer for legal documents.
/// Produces clean Markdown output for debugging and previewing.
module MarkdownRenderer =

    let private renderSectionRec (sb: StringBuilder) (section: Section) (depth: int) =
        let rec render (sb: StringBuilder) (section: Section) (depth: int) =
            if not (System.String.IsNullOrWhiteSpace section.HeadingText) then
                let level = max (HeadingLevel.toInt section.HeadingLevel) (depth + 1)
                let prefix = System.String('#', min level 6)
                let heading =
                    match section.NumberingPrefix with
                    | Some np -> np + " " + section.HeadingText
                    | None -> section.HeadingText
                sb.AppendLine(sprintf "%s %s" prefix heading) |> ignore
                sb.AppendLine() |> ignore

            for block in section.Content do
                if System.String.IsNullOrEmpty block.Text then
                    sb.AppendLine() |> ignore
                else
                    sb.AppendLine(block.Text) |> ignore
            sb.AppendLine() |> ignore

            for sub in section.Subsections do
                render sb sub (depth + 1)

        render sb section depth

    /// Render a LegalDocument as Markdown text.
    let renderMarkdown (doc: LegalDocument) : string =
        let sb = StringBuilder()

        // Caption
        match doc.Caption with
        | Some caption ->
            for line in caption.Lines do
                if not (System.String.IsNullOrEmpty line.Text) then
                    if line.Bold then
                        sb.AppendLine(sprintf "**%s**" line.Text) |> ignore
                    else
                        sb.AppendLine(line.Text) |> ignore
                else
                    sb.AppendLine() |> ignore
            sb.AppendLine() |> ignore
            sb.AppendLine("---") |> ignore
            sb.AppendLine() |> ignore
        | None -> ()

        // Sections
        for section in doc.Sections do
            renderSectionRec sb section 0

        // Signature block
        match doc.SignatureBlock with
        | Some sig' ->
            sb.AppendLine() |> ignore
            sb.AppendLine("---") |> ignore
            sb.AppendLine() |> ignore
            sb.AppendLine("Respectfully submitted,") |> ignore
            sb.AppendLine() |> ignore
            sb.AppendLine(sprintf "**%s**  " sig'.AttorneyName) |> ignore
            sb.AppendLine(sprintf "State Bar No. %s  " sig'.BarNumber) |> ignore
            match sig'.Firm with
            | Some firm -> sb.AppendLine(sprintf "%s  " firm) |> ignore
            | None -> ()
            sb.AppendLine(sprintf "%s  " sig'.Address) |> ignore
            sb.AppendLine(sprintf "Phone: %s  " sig'.Phone) |> ignore
            sb.AppendLine(sprintf "Email: %s" sig'.Email) |> ignore
        | None -> ()

        // Certifications
        for cert in doc.Certifications do
            sb.AppendLine() |> ignore
            sb.AppendLine("---") |> ignore
            sb.AppendLine() |> ignore
            renderSectionRec sb cert 0

        sb.ToString().TrimEnd()
