// Types mirroring `schemas/json-schema/*.schema.json`.
//
// Hand-written for v1 alpha so the taskpane has something concrete to
// import; v1.5 swaps in `openapi-typescript-codegen` driven by
// `schemas/openapi.yaml` so adding or changing a Pydantic field
// regenerates the TS types on the next build. The
// test_schema_export.py CI test on the server side guards against
// drift between the schemas and the Python models, so the hand-mirror
// here only needs maintenance when the JSON schemas move.

export type Severity = "error" | "warning" | "info";
export type Provenance = "rule" | "ml" | "llm" | "hybrid";
export type SuggestionKind = "replace" | "insert" | "delete" | "reformat";
export type SegmentKind =
  | "heading"
  | "paragraph"
  | "footnote"
  | "block_quote"
  | "table_cell";

export interface CharRange {
  segment_id: string;
  start: number;
  end: number;
}

export interface ObservedStyle {
  font_name?: string | null;
  font_size_pt?: number | null;
  line_spacing?: number | null;
  alignment?: string | null;
  indent_inches?: number | null;
  bold?: boolean | null;
  italic?: boolean | null;
  margin_top_inches?: number | null;
  margin_bottom_inches?: number | null;
  margin_left_inches?: number | null;
  margin_right_inches?: number | null;
}

export interface Suggestion {
  kind: SuggestionKind;
  range: CharRange;
  new_text?: string | null;
  new_style?: ObservedStyle | null;
  rationale: string;
  auto_apply_safe: boolean;
}

export interface Finding {
  id: string;
  segment_id: string;
  checker_id: string;
  rule_id: string;
  severity: Severity;
  message: string;
  evidence: Record<string, unknown>;
  suggestion?: Suggestion | null;
  confidence: number;
  provenance: Provenance;
}

export interface LLMCostBreakdown {
  total_usd_cents: number;
  by_prompt: Record<string, number>;
  by_provider: Record<string, number>;
}

export interface QualityReport {
  document_id: string;
  run_id: string;
  findings: Finding[];
  score: number;
  applied_suggestions: string[];
  remaining_findings: string[];
  cost: LLMCostBreakdown;
  started_at: string;
  finished_at?: string | null;
}

// API request/response shapes (not in JSON schemas — straight from openapi.yaml).

export interface DocumentRef {
  document_id: string;
}

export interface CreateRunRequest {
  document_id: string;
  policy_id?: string | null;
  mode?: "report" | "autofix";
}

export interface RunRef {
  run_id: string;
  status_url: string;
  status: string;
}

export interface PublicKeyResponse {
  org_id: string;
  public_key_pem: string;
}

export interface EncryptedUploadRequest {
  ciphertext_b64: string;
  nonce_b64: string;
  wrapped_dek_b64: string;
  sha256: string;
  original_filename?: string | null;
}
