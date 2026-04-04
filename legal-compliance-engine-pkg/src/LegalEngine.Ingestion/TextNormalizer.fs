namespace LegalEngine.Ingestion

/// Ingestion-level text normalization that delegates to core parsing utilities.
/// Re-exports stripUnicodeControl and normalizeLineEndings for ingestion callers.
module TextNormalizer =

    /// Remove Unicode control characters except standard whitespace (\n, \r, \t, space).
    let stripUnicodeControl (s: string) : string =
        LegalEngine.Parsing.TextNormalizer.stripUnicodeControl s

    /// Normalize line endings to Unix-style (\n).
    let normalizeLineEndings (s: string) : string =
        LegalEngine.Parsing.TextNormalizer.normalizeLineEndings s
