namespace LegalEngine.Api

open System
open Microsoft.AspNetCore.Http

/// Handler for POST /generate/caption — generate a formatted caption block.
module CaptionHandler =

    /// POST /generate/caption handler.
    let handle (req: CaptionRequest) : IResult =
        // TODO: Wire up the full caption engine from LegalEngine.Rules
        // For now, build a simple caption from the request fields

        let courtLine = req.CourtName.ToUpper()
        let caseNumberLine = sprintf "Case No. %s" req.CaseNumber

        let partyLines =
            if req.Parties <> null && req.Parties.Length > 0 then
                let grouped =
                    req.Parties
                    |> Array.groupBy (fun p -> p.Role.ToLowerInvariant())

                let lines = ResizeArray<string>()
                let mutable first = true
                for (role, parties) in grouped do
                    if not first then
                        lines.Add("v.")
                    first <- false
                    for p in parties do
                        lines.Add(p.Name.ToUpper())
                        let designation =
                            if String.IsNullOrWhiteSpace p.Designation then
                                p.Role
                            else
                                p.Designation
                        lines.Add(sprintf "        %s," designation)
                lines.ToArray() |> Array.toList
            else
                []

        let titleLine = req.DocumentTitle.ToUpper()

        let allLines =
            [ courtLine; ""; caseNumberLine; "" ]
            @ partyLines
            @ [ ""; titleLine ]

        let captionText = String.Join(Environment.NewLine, allLines)

        let response : CaptionResponse =
            { CaptionText = captionText
              Lines = allLines |> Array.ofList }
        Results.Ok(response)
