namespace LegalEngine.Parsing

open System.Text.RegularExpressions
open LegalEngine.Domain

/// Heading detection heuristics for plain text legal documents.
module HeadingDetector =

    /// Detect whether a line is a heading and what level.
    /// Heuristics:
    /// - ALL CAPS, short, no ending punctuation except period -> Level1
    /// - Starts with Roman numeral prefix -> Level2
    /// - Starts with capital letter prefix (A., B.) -> Level3
    /// - Starts with arabic number prefix (1., 2.) -> Level4
    let detectHeadingLevel (line: string) : HeadingLevel option =
        // Too long for a heading
        if line.Length > 150 then
            None
        else
            // Check for numbering prefix first (more specific)
            let (prefix, remaining) = NumberingUtils.stripNumberingPrefix line

            if not (System.String.IsNullOrEmpty(prefix)) then
                let prefixClean = prefix.TrimEnd('.')
                if Regex.IsMatch(prefixClean, @"^[IVXLC]+$", RegexOptions.IgnoreCase) then
                    // Roman numeral -> Level 2
                    if remaining.Length < 120 then Some HeadingLevel.Level2
                    else None
                elif Regex.IsMatch(prefixClean, @"^[A-Z]$") then
                    // Single capital letter -> Level 3
                    if remaining.Length < 120 then Some HeadingLevel.Level3
                    else None
                elif Regex.IsMatch(prefixClean, @"^\d+$") then
                    // Arabic number -> Level 4
                    if remaining.Length < 120 then Some HeadingLevel.Level4
                    else None
                else
                    None
            else
                // ALL CAPS check for Level 1
                let alphaChars = line |> Seq.filter System.Char.IsLetter |> Seq.toList
                if alphaChars.Length >= 3
                   && alphaChars |> List.forall System.Char.IsUpper
                   && line.Length < 80
                   && not (line.EndsWith(",")) then
                    Some HeadingLevel.Level1
                else
                    None
