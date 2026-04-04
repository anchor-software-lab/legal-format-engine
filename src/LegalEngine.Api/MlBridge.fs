namespace LegalEngine.Api

/// HTTP bridge to the Python ML engine (anchor-ml-engine).
///
/// The ML engine runs as a separate service (e.g., on port 8000).
/// This module provides typed F# access to its endpoints.
///
/// Used for:
/// - Real-time TF model predictions (heading classification, format prediction)
/// - Triggering learning on uploaded documents
/// - Fetching learned patterns and style profiles
///
/// All calls are optional — the F# engine works without the ML service.
/// When the ML service is unavailable, calls return None/empty results.

open System
open System.Net.Http
open System.Text
open System.Text.Json
open System.Text.Json.Serialization
open System.Threading.Tasks
open LegalEngine.Rules


// ── Response DTOs ─────────────────────────────────────────────────

[<CLIMutable>]
type MlHealthResponse = {
    [<JsonPropertyName("status")>] Status: string
    [<JsonPropertyName("version")>] Version: string
}

[<CLIMutable>]
type MlLearnResponse = {
    [<JsonPropertyName("document_count")>] DocumentCount: int
    [<JsonPropertyName("font_name")>] FontName: string
    [<JsonPropertyName("font_size_pt")>] FontSizePt: Nullable<float>
    [<JsonPropertyName("margin_top")>] MarginTop: Nullable<float>
    [<JsonPropertyName("margin_bottom")>] MarginBottom: Nullable<float>
    [<JsonPropertyName("margin_left")>] MarginLeft: Nullable<float>
    [<JsonPropertyName("margin_right")>] MarginRight: Nullable<float>
    [<JsonPropertyName("line_spacing")>] LineSpacing: Nullable<float>
    [<JsonPropertyName("first_line_indent")>] FirstLineIndent: Nullable<float>
}

[<CLIMutable>]
type MlHeadingPrediction = {
    [<JsonPropertyName("level")>] Level: int
    [<JsonPropertyName("confidence")>] Confidence: float
}

[<CLIMutable>]
type MlStyleResponse = {
    [<JsonPropertyName("identifier")>] Identifier: string
    [<JsonPropertyName("profile_type")>] ProfileType: string
    [<JsonPropertyName("document_count")>] DocumentCount: int
    [<JsonPropertyName("first_line_indent")>] FirstLineIndent: Nullable<float>
    [<JsonPropertyName("block_quote_indent")>] BlockQuoteIndent: Nullable<float>
    [<JsonPropertyName("confidence")>] Confidence: float
}

[<CLIMutable>]
type MlResolveResponse = {
    [<JsonPropertyName("font")>] Font: string
    [<JsonPropertyName("font_size_pt")>] FontSizePt: float
    [<JsonPropertyName("margin_top_inches")>] MarginTop: float
    [<JsonPropertyName("margin_bottom_inches")>] MarginBottom: float
    [<JsonPropertyName("margin_left_inches")>] MarginLeft: float
    [<JsonPropertyName("margin_right_inches")>] MarginRight: float
    [<JsonPropertyName("line_spacing")>] LineSpacing: string
    [<JsonPropertyName("first_line_indent_inches")>] FirstLineIndent: float
}


// ── Bridge Client ─────────────────────────────────────────────────

type MlBridgeClient(baseUrl: string) =

    let client = new HttpClient(BaseAddress = Uri(baseUrl))
    let jsonOpts =
        let o = JsonSerializerOptions()
        o.PropertyNameCaseInsensitive <- true
        o

    /// Check if the ML service is available.
    member _.IsAvailableAsync() : Task<bool> =
        task {
            try
                let! resp = client.GetAsync("/api/health")
                return resp.IsSuccessStatusCode
            with _ ->
                return false
        }

    /// Trigger learning on stored documents for a jurisdiction.
    member _.LearnAsync(jurisdiction: string) : Task<MlLearnResponse option> =
        task {
            try
                let! resp = client.GetAsync($"/api/ml/learn?jurisdiction={jurisdiction}")
                if resp.IsSuccessStatusCode then
                    let! json = resp.Content.ReadAsStringAsync()
                    let result = JsonSerializer.Deserialize<MlLearnResponse>(json, jsonOpts)
                    return Some result
                else
                    return None
            with _ ->
                return None
        }

    /// Get a suggested YAML ruleset from ML patterns.
    member _.SuggestRulesetAsync(jurisdiction: string) : Task<string option> =
        task {
            try
                let! resp = client.GetAsync($"/api/ml/suggest-ruleset?jurisdiction={jurisdiction}")
                if resp.IsSuccessStatusCode then
                    let! json = resp.Content.ReadAsStringAsync()
                    // The response has a "yaml" field
                    let doc = JsonDocument.Parse(json)
                    let yaml = doc.RootElement.GetProperty("yaml").GetString()
                    return Some yaml
                else
                    return None
            with _ ->
                return None
        }

    /// Get a style profile for an author or firm.
    member _.GetStyleAsync(identifier: string) : Task<StyleProfile option> =
        task {
            try
                let encoded = Uri.EscapeDataString(identifier)
                let! resp = client.GetAsync($"/api/ml/styles/{encoded}")
                if resp.IsSuccessStatusCode then
                    let! json = resp.Content.ReadAsStringAsync()
                    let raw = JsonSerializer.Deserialize<MlStyleResponse>(json, jsonOpts)
                    return Some {
                        Identifier = raw.Identifier
                        ProfileType = raw.ProfileType
                        FirstLineIndent =
                            if raw.FirstLineIndent.HasValue then Some raw.FirstLineIndent.Value
                            else None
                        BlockQuoteIndent =
                            if raw.BlockQuoteIndent.HasValue then Some raw.BlockQuoteIndent.Value
                            else None
                        SectionSpacing = None
                        Justify = None
                        DocumentCount = raw.DocumentCount
                        Confidence = raw.Confidence
                    }
                else
                    return None
            with _ ->
                return None
        }

    /// Resolve final format using the ML service's hierarchy resolution.
    member _.ResolveFormatAsync
        (jurisdiction: string,
         courtLevel: string,
         documentType: string,
         ?author: string,
         ?firm: string)
        : Task<MlResolveResponse option> =
        task {
            try
                let mutable url = $"/api/ml/resolve?jurisdiction={jurisdiction}&document_type={documentType}"
                match author with Some a -> url <- url + $"&author={Uri.EscapeDataString a}" | None -> ()
                match firm with Some f -> url <- url + $"&firm={Uri.EscapeDataString f}" | None -> ()
                let! resp = client.GetAsync(url)
                if resp.IsSuccessStatusCode then
                    let! json = resp.Content.ReadAsStringAsync()
                    return Some (JsonSerializer.Deserialize<MlResolveResponse>(json, jsonOpts))
                else
                    return None
            with _ ->
                return None
        }

    /// Upload a document for ML ingestion.
    member _.IngestAsync(filePath: string, ?jurisdiction: string, ?author: string, ?firm: string) : Task<bool> =
        task {
            try
                use content = new MultipartFormDataContent()
                let fileBytes = IO.File.ReadAllBytes(filePath)
                let fileName = IO.Path.GetFileName(filePath)
                content.Add(new ByteArrayContent(fileBytes), "file", fileName)
                match jurisdiction with Some j -> content.Add(new StringContent(j), "jurisdiction") | None -> ()
                match author with Some a -> content.Add(new StringContent(a), "author") | None -> ()
                match firm with Some f -> content.Add(new StringContent(f), "firm") | None -> ()
                let! resp = client.PostAsync("/api/ml/ingest", content)
                return resp.IsSuccessStatusCode
            with _ ->
                return false
        }

    interface IDisposable with
        member _.Dispose() = client.Dispose()
