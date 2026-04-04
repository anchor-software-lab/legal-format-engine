namespace LegalEngine.Rules

/// Section validation, reordering, and insertion engine.
/// Validates required sections exist, checks ordering, handles
/// group constraints, and inserts stubs for missing sections.

open LegalEngine.Domain

module SectionRules =

    // ── Alias & Fuzzy Matching ──────────────────────────────────────

    /// Normalize a string for comparison: lowercase, trim, collapse whitespace.
    let private normalizeForMatching (s: string) =
        if System.String.IsNullOrWhiteSpace s then ""
        else
            s.Trim().ToLowerInvariant()
            |> fun t -> System.Text.RegularExpressions.Regex.Replace(t, @"\s+", " ")

    /// Build a mapping of section_id -> [canonical_name; aliases...].
    let buildAliasMap (ruleset: Ruleset) : Map<string, string list> =
        ruleset.RequiredSections
        |> List.map (fun req ->
            req.Id, req.CanonicalName :: req.Aliases)
        |> Map.ofList

    /// Fuzzy-match a heading against known sections.
    /// Returns Some section_id if matched, None otherwise.
    let fuzzyMatchSection (heading: string) (aliasMap: Map<string, string list>) : string option =
        let normalized = normalizeForMatching heading
        if System.String.IsNullOrWhiteSpace normalized then None
        else
            aliasMap
            |> Map.tryPick (fun sectionId names ->
                let matched =
                    names |> List.exists (fun name ->
                        normalizeForMatching name = normalized)
                if matched then Some sectionId else None)

    // ── Validation ──────────────────────────────────────────────────

    /// Check group constraints: at least one section in each group must exist.
    let private checkGroups (ruleset: Ruleset) (matchedIds: Set<string>) : Finding list =
        let groups =
            ruleset.RequiredSections
            |> List.choose (fun req ->
                match req.Group with
                | Some g -> Some (g, req)
                | None -> None)
            |> List.groupBy fst
            |> List.map (fun (groupName, members) -> groupName, members |> List.map snd)

        groups
        |> List.choose (fun (groupName, members) ->
            let groupMatched = members |> List.exists (fun m -> matchedIds.Contains m.Id)
            if groupMatched then None
            else
                let names = members |> List.map (fun m -> m.CanonicalName) |> String.concat ", "
                Some (Finding.warning "MISSING_SECTION_GROUP"
                    (sprintf "At least one of these sections is required: %s" names)))

    /// Check if sections are in correct order.
    let private checkOrder (sections: Section list) (ruleset: Ruleset) (aliasMap: Map<string, string list>) : Finding list =
        let ruleOrder =
            ruleset.RequiredSections
            |> List.map (fun req -> req.Id, req.Order)
            |> Map.ofList

        let sectionOrders =
            sections
            |> List.choose (fun section ->
                match fuzzyMatchSection section.HeadingText aliasMap with
                | Some matchId ->
                    match Map.tryFind matchId ruleOrder with
                    | Some order -> Some (matchId, order)
                    | None -> None
                | None -> None)

        // Check monotonically increasing
        let rec checkPairs pairs =
            match pairs with
            | (id1, ord1) :: ((id2, ord2) :: _ as rest) ->
                if ord2 < ord1 then
                    [ Finding.warning "WRONG_ORDER"
                        (sprintf "Section '%s' appears before '%s' but should come after it." id2 id1)
                      |> Finding.withFix "Reorder sections to match ruleset order" ]
                else
                    checkPairs rest
            | _ -> []

        checkPairs sectionOrders

    /// Validate that required sections exist in the document.
    /// Returns findings for missing, unknown, misordered sections.
    let validateSections (ruleset: Ruleset) (doc: LegalDocument) : Finding list =
        let aliasMap = buildAliasMap ruleset
        let matchedIds =
            doc.Sections
            |> List.choose (fun section ->
                fuzzyMatchSection section.HeadingText aliasMap)
            |> Set.ofList

        // Unknown sections
        let unknownFindings =
            doc.Sections
            |> List.choose (fun section ->
                if System.String.IsNullOrWhiteSpace section.HeadingText then None
                elif section.Id = "preamble" then None
                else
                    match fuzzyMatchSection section.HeadingText aliasMap with
                    | Some _ -> None
                    | None ->
                        Some (Finding.info "UNKNOWN_SECTION"
                            (sprintf "Section '%s' does not match any known section type." section.HeadingText)))

        // Missing required sections
        let missingFindings =
            ruleset.RequiredSections
            |> List.choose (fun req ->
                if req.Required && not (matchedIds.Contains req.Id) then
                    Some (Finding.warning "MISSING_SECTION"
                        (sprintf "Required section '%s' is missing." req.CanonicalName)
                        |> Finding.withFix (sprintf "Insert stub section for '%s'" req.CanonicalName))
                else
                    None)

        // Group constraints
        let groupFindings = checkGroups ruleset matchedIds

        // Order check
        let orderFindings = checkOrder doc.Sections ruleset aliasMap

        unknownFindings @ missingFindings @ groupFindings @ orderFindings

    // ── Reordering ──────────────────────────────────────────────────

    /// Reorder sections to match the canonical order defined in the ruleset.
    /// Matched sections are placed in rule order. Unmatched sections
    /// are appended at the end (never discarded).
    let reorderSections (ruleset: Ruleset) (sections: Section list) : Section list =
        let aliasMap = buildAliasMap ruleset
        let ruleOrder =
            ruleset.RequiredSections
            |> List.map (fun req -> req.Id, req.Order)
            |> Map.ofList

        // Map each section to its rule id (if matched)
        let mutable matchedMap: Map<string, Section> = Map.empty
        let mutable unmatched: Section list = []

        for section in sections do
            match fuzzyMatchSection section.HeadingText aliasMap with
            | Some matchId when not (matchedMap.ContainsKey matchId) ->
                matchedMap <- matchedMap |> Map.add matchId section
            | _ ->
                unmatched <- section :: unmatched

        // Build reordered list: matched in rule order, then unmatched
        let ordered =
            ruleset.RequiredSections
            |> List.sortBy (fun r -> r.Order)
            |> List.choose (fun req ->
                Map.tryFind req.Id matchedMap)

        ordered @ (List.rev unmatched)

    // ── Insert Missing Sections ─────────────────────────────────────

    /// Insert stub sections for any missing required sections at the correct position.
    let insertMissingSections (ruleset: Ruleset) (sections: Section list) : Section list =
        let aliasMap = buildAliasMap ruleset
        let ruleOrder =
            ruleset.RequiredSections
            |> List.map (fun req -> req.Id, req.Order)
            |> Map.ofList

        let existingIds =
            sections
            |> List.choose (fun section ->
                fuzzyMatchSection section.HeadingText aliasMap)
            |> Set.ofList

        let missingReqs =
            ruleset.RequiredSections
            |> List.filter (fun req -> req.Required && not (existingIds.Contains req.Id))

        let mutable result = sections

        for req in missingReqs do
            let headingLevel =
                HeadingLevel.fromInt req.HeadingLevel
                |> Option.defaultValue HeadingLevel.Level1

            let stub: Section =
                { Id = req.Id
                  HeadingText = req.CanonicalName.ToUpperInvariant()
                  HeadingLevel = headingLevel
                  NumberingPrefix = None
                  Content = [ ContentBlock.text (sprintf "[%s - TO BE COMPLETED]" req.CanonicalName) ]
                  Subsections = []
                  IsGenerated = true }

            // Find the correct insert position based on rule order
            let targetOrder = req.Order
            let insertIdx =
                result
                |> List.tryFindIndex (fun section ->
                    match fuzzyMatchSection section.HeadingText aliasMap with
                    | Some matchId ->
                        match Map.tryFind matchId ruleOrder with
                        | Some order -> order > targetOrder
                        | None -> false
                    | None -> false)
                |> Option.defaultValue (List.length result)

            let before = result |> List.take insertIdx
            let after = result |> List.skip insertIdx
            result <- before @ [ stub ] @ after

        result
