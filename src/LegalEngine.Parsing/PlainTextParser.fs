namespace LegalEngine.Parsing

open LegalEngine.Domain

/// Plain text parser for legal documents.
/// Converts unstructured text into a LegalDocument by detecting
/// headings, sections, and content blocks heuristically.
module PlainTextParser =

    /// Parse plain text into a LegalDocument with best-effort section detection.
    /// The parser identifies headings heuristically and groups content
    /// into sections. It does NOT extract metadata - that must be
    /// provided separately.
    let parsePlainText (text: string) : LegalDocument =
        let text = TextNormalizer.stripUnicodeControl text
        let lines = text.Split([| '\n' |]) |> Array.toList
        let classified = SectionBuilder.classifyLines lines
        let sections = SectionBuilder.buildSections classified

        { LegalDocument.empty with
            Sections = sections
            RawText = Some text }
