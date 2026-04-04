namespace LegalEngine.Parsing

open System.Text.RegularExpressions
open LegalEngine.Domain

/// Line classification and section building for plain text legal documents.
module SectionBuilder =

    /// A classified line: either a heading with a level, or content.
    type ClassifiedLine =
        | HeadingLine of text: string * level: HeadingLevel
        | ContentLine of text: string

    /// Classify each line as a heading or content.
    let classifyLines (lines: string list) : ClassifiedLine list =
        lines
        |> List.map (fun line ->
            let stripped = line.Trim()
            if System.String.IsNullOrEmpty(stripped) then
                ContentLine ""
            else
                match HeadingDetector.detectHeadingLevel stripped with
                | Some level -> HeadingLine(stripped, level)
                | None -> ContentLine stripped)

    /// Trim leading and trailing empty content blocks from a list.
    let private trimContent (blocks: ContentBlock list) : ContentBlock list =
        let trimFront =
            blocks |> List.skipWhile (fun b -> System.String.IsNullOrWhiteSpace(b.Text))
        trimFront
        |> List.rev
        |> List.skipWhile (fun b -> System.String.IsNullOrWhiteSpace(b.Text))
        |> List.rev

    /// Create a section from a heading and content blocks.
    let private makeSection (heading: string) (level: HeadingLevel) (content: ContentBlock list) (index: int) : Section =
        let slug =
            let cleaned = Regex.Replace(heading.ToLower(), @"[^\w\s]", "")
            let s = Regex.Replace(cleaned.Trim(), @"\s+", "_")
            if System.String.IsNullOrEmpty(s) then sprintf "section_%d" index
            else s
        { Id = slug
          HeadingText = heading
          HeadingLevel = level
          NumberingPrefix = None
          Content = trimContent content
          Subsections = []
          IsGenerated = false }

    /// Build a flat list of sections from classified lines.
    /// Groups content lines under the preceding heading.
    /// Content before any heading goes into a preamble section.
    let buildSections (classified: ClassifiedLine list) : Section list =
        let mutable sections: Section list = []
        let mutable currentContent: ContentBlock list = []
        let mutable currentHeading: string option = None
        let mutable currentLevel: HeadingLevel option = None
        let mutable sectionCounter = 0

        for cl in classified do
            match cl with
            | HeadingLine(text, level) ->
                // Save previous section if there was a heading
                match currentHeading with
                | Some heading ->
                    let lvl = currentLevel |> Option.defaultValue HeadingLevel.Level1
                    sections <- sections @ [ makeSection heading lvl currentContent sectionCounter ]
                    sectionCounter <- sectionCounter + 1
                | None ->
                    if currentContent |> List.exists (fun b -> not (System.String.IsNullOrWhiteSpace(b.Text))) then
                        let preamble =
                            { Id = "preamble"
                              HeadingText = ""
                              HeadingLevel = HeadingLevel.Level1
                              NumberingPrefix = None
                              Content = trimContent currentContent
                              Subsections = []
                              IsGenerated = false }
                        sections <- sections @ [ preamble ]
                        sectionCounter <- sectionCounter + 1
                currentHeading <- Some text
                currentLevel <- Some level
                currentContent <- []

            | ContentLine text ->
                currentContent <- currentContent @ [ ContentBlock.text text ]

        // Don't forget the last section
        match currentHeading with
        | Some heading ->
            let lvl = currentLevel |> Option.defaultValue HeadingLevel.Level1
            sections <- sections @ [ makeSection heading lvl currentContent sectionCounter ]
        | None ->
            if currentContent |> List.exists (fun b -> not (System.String.IsNullOrWhiteSpace(b.Text))) then
                let preamble =
                    { Id = "preamble"
                      HeadingText = ""
                      HeadingLevel = HeadingLevel.Level1
                      NumberingPrefix = None
                      Content = trimContent currentContent
                      Subsections = []
                      IsGenerated = false }
                sections <- sections @ [ preamble ]

        sections
