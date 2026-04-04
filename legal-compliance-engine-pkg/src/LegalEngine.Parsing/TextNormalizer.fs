namespace LegalEngine.Parsing

open System
open System.Globalization
open System.Text.RegularExpressions

/// Text normalization utilities for ingested documents.
module TextNormalizer =

    /// Remove Unicode control characters except standard whitespace (\n, \r, \t, space).
    let stripUnicodeControl (s: string) : string =
        s
        |> String.collect (fun c ->
            let cat = CharUnicodeInfo.GetUnicodeCategory(c)
            if cat = UnicodeCategory.Control && c <> '\n' && c <> '\r' && c <> '\t' && c <> ' ' then
                ""
            else
                string c)

    /// Normalize line endings to Unix-style (\n).
    let normalizeLineEndings (s: string) : string =
        s.Replace("\r\n", "\n").Replace("\r", "\n")
