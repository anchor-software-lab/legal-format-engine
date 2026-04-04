namespace LegalEngine.Parsing

open System.Text.RegularExpressions

/// Numbering conversion utilities for legal document headings.
module NumberingUtils =

    let private romanValues =
        [ (1000, "M"); (900, "CM"); (500, "D"); (400, "CD")
          (100, "C"); (90, "XC"); (50, "L"); (40, "XL")
          (10, "X"); (9, "IX"); (5, "V"); (4, "IV"); (1, "I") ]

    let private romanPattern =
        Regex(@"^(M{0,3})(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$", RegexOptions.IgnoreCase)

    /// Matches leading numbering prefixes: "I.", "II.", "A.", "1.", "a.", "(1)", "(a)"
    let numberingPrefixPattern =
        Regex(
            @"^(?:" +
            @"[IVXLC]+\.\s*" +        // Roman: I., II., III.
            @"|[A-Z]\.\s*" +           // Alpha upper: A., B., C.
            @"|[a-z]\.\s*" +           // Alpha lower: a., b., c.
            @"|\d+\.\s*" +             // Arabic: 1., 2., 3.
            @"|\(\d+\)\s*" +           // Paren arabic: (1), (2)
            @"|\([a-z]\)\s*" +         // Paren alpha: (a), (b)
            @")",
            RegexOptions.IgnoreCase)

    /// Convert a positive integer to an uppercase Roman numeral string.
    let intToRoman (n: int) : string =
        if n < 1 then
            invalidArg "n" (sprintf "Roman numerals must be positive, got %d" n)
        let mutable remaining = n
        let result = System.Text.StringBuilder()
        for (value, numeral) in romanValues do
            while remaining >= value do
                result.Append(numeral) |> ignore
                remaining <- remaining - value
        result.ToString()

    /// Convert a Roman numeral string to an integer.
    let romanToInt (s: string) : int =
        let s = s.Trim().ToUpper()
        if System.String.IsNullOrEmpty(s) || not (romanPattern.IsMatch(s)) then
            invalidArg "s" (sprintf "Invalid Roman numeral: '%s'" s)
        let romanMap (c: char) =
            match c with
            | 'I' -> 1 | 'V' -> 5 | 'X' -> 10 | 'L' -> 50
            | 'C' -> 100 | 'D' -> 500 | 'M' -> 1000
            | _ -> 0
        let mutable total = 0
        for i in 0 .. s.Length - 1 do
            let value = romanMap s.[i]
            if i + 1 < s.Length && value < romanMap s.[i + 1] then
                total <- total - value
            else
                total <- total + value
        total

    /// Convert a 1-based index to uppercase letter(s). 1 -> "A", 26 -> "Z", 27 -> "AA"
    let intToAlphaUpper (n: int) : string =
        if n < 1 then
            invalidArg "n" (sprintf "Index must be positive, got %d" n)
        let mutable remaining = n
        let result = System.Collections.Generic.List<char>()
        while remaining > 0 do
            remaining <- remaining - 1
            result.Add(char (65 + (remaining % 26)))
            remaining <- remaining / 26
        result.Reverse()
        System.String(result.ToArray())

    /// Convert a 1-based index to lowercase letter(s). 1 -> "a", 26 -> "z", 27 -> "aa"
    let intToAlphaLower (n: int) : string =
        (intToAlphaUpper n).ToLower()

    /// Generate a numbering prefix for a given 1-based index.
    /// numberingType: "roman", "alpha_upper", "alpha_lower", "arabic", or None.
    let generatePrefix (index: int) (numberingType: string option) : string =
        match numberingType with
        | None -> ""
        | Some typ ->
            match typ with
            | "roman" -> sprintf "%s." (intToRoman index)
            | "alpha_upper" -> sprintf "%s." (intToAlphaUpper index)
            | "alpha_lower" -> sprintf "%s." (intToAlphaLower index)
            | "arabic" -> sprintf "%d." index
            | other -> invalidArg "numberingType" (sprintf "Unknown numbering type: '%s'" other)

    /// Strip a leading numbering prefix from heading text.
    /// Returns (prefix, remainingText). Returns ("", text) if no prefix is found.
    let stripNumberingPrefix (text: string) : string * string =
        if System.String.IsNullOrEmpty(text) then
            ("", "")
        else
            let m = numberingPrefixPattern.Match(text)
            if m.Success then
                let prefix = m.Value.Trim()
                let remaining = text.Substring(m.Length).Trim()
                (prefix, remaining)
            else
                ("", text.Trim())

    /// Active patterns for classifying numbering prefixes.
    let (|RomanPrefix|AlphaPrefix|ArabicPrefix|NoPrefix|) (text: string) =
        let (prefix, _remaining) = stripNumberingPrefix text
        if System.String.IsNullOrEmpty(prefix) then
            NoPrefix
        else
            let prefixClean = prefix.TrimEnd('.').Trim('(', ')')
            if Regex.IsMatch(prefixClean, @"^[IVXLC]+$", RegexOptions.IgnoreCase) then
                RomanPrefix
            elif Regex.IsMatch(prefixClean, @"^[A-Za-z]+$") then
                AlphaPrefix
            elif Regex.IsMatch(prefixClean, @"^\d+$") then
                ArabicPrefix
            else
                NoPrefix
