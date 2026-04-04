namespace LegalEngine.Parsing

open System
open System.Text.RegularExpressions

/// Text processing utilities for legal documents.
module TextUtils =

    /// Words that should stay lowercase in title case (unless first/last).
    let private titleCaseExceptions =
        set [
            "a"; "an"; "the"; "and"; "but"; "or"; "nor"; "for"; "yet"; "so"
            "at"; "by"; "in"; "of"; "on"; "to"; "up"; "as"; "is"; "if"
            "v."; "vs."; "v"
        ]

    /// Convert text to uppercase.
    let toUpper (s: string) : string = s.ToUpper()

    /// Convert text to title case with legal-aware exceptions.
    let toTitleCase (s: string) : string =
        let words = s.Trim().Split([| ' ' |], StringSplitOptions.RemoveEmptyEntries)
        if words.Length = 0 then s
        else
            let capitalize (w: string) =
                if w.Length = 0 then w
                else (Char.ToUpper(w.[0])).ToString() + w.Substring(1).ToLower()
            words
            |> Array.mapi (fun i word ->
                let lower = word.ToLower()
                if i = 0 || i = words.Length - 1 then
                    capitalize word
                elif titleCaseExceptions.Contains(lower) then
                    lower
                else
                    capitalize word)
            |> String.concat " "

    /// Convert text to sentence case (first letter capitalized, rest lowercase).
    let toSentenceCase (s: string) : string =
        let s = s.Trim()
        if String.IsNullOrEmpty(s) then s
        else (Char.ToUpper(s.[0])).ToString() + s.Substring(1).ToLower()

    /// Collapse multiple whitespace characters into single spaces and strip.
    let normalizeWhitespace (s: string) : string =
        Regex.Replace(s, @"\s+", " ").Trim()

    /// Normalize a string for fuzzy heading comparison.
    /// Strips numbering prefixes, lowercases, removes punctuation, collapses whitespace.
    let normalizeForMatching (s: string) : string =
        let (_prefix, text) = NumberingUtils.stripNumberingPrefix s
        let text = text.ToLower()
        // Remove punctuation except periods in abbreviations
        let text = Regex.Replace(text, @"[^\w\s.]", "")
        // Remove trailing periods
        let text = text.TrimEnd('.')
        normalizeWhitespace text

    /// Match a heading against canonical names and their aliases.
    /// candidates: Map from section_id to list of acceptable names/aliases.
    /// Returns the matched section_id, or None.
    let fuzzyHeadingMatch (heading: string) (candidates: Map<string, string list>) : string option =
        if String.IsNullOrWhiteSpace(heading) then
            None
        else
            let normalized = normalizeForMatching heading
            if String.IsNullOrEmpty(normalized) then
                None
            else
                // First pass: exact match after normalization
                let exactMatch =
                    candidates
                    |> Map.tryPick (fun sectionId names ->
                        if names |> List.exists (fun name -> normalizeForMatching name = normalized) then
                            Some sectionId
                        else
                            None)
                match exactMatch with
                | Some _ -> exactMatch
                | None ->
                    // Second pass: substring containment
                    candidates
                    |> Map.tryPick (fun sectionId names ->
                        if names |> List.exists (fun name ->
                            let normName = normalizeForMatching name
                            normName.Contains(normalized) || normalized.Contains(normName)) then
                            Some sectionId
                        else
                            None)

    /// Heuristic check if a line looks like a section heading.
    let isLikelyHeading (line: string) : bool =
        let line = line.Trim()
        if String.IsNullOrEmpty(line) then false
        elif line.Length > 150 then false
        elif line.ToUpper() = line && line.Length < 80 then
            // All caps and short -> likely heading (check it has alpha chars)
            line |> Seq.exists Char.IsLetter
        elif NumberingUtils.numberingPrefixPattern.IsMatch(line) && line.Length < 120 then
            true
        else
            false
