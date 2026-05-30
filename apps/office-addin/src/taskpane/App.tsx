import { useCallback, useMemo, useState } from "react";
import {
  Body1,
  Button,
  Caption1,
  Card,
  CardHeader,
  Divider,
  Spinner,
  Subtitle1,
  Subtitle2,
  Switch,
  Text,
} from "@fluentui/react-components";

import { AnchorClient } from "../api/client";
import type { Finding, QualityReport, Severity } from "../api/types";

// Configuration is read from Vite env at build time; in a real deploy
// the operator sets ANCHOR_API_URL / ANCHOR_API_KEY via secret env.
const API_BASE_URL = import.meta.env.VITE_ANCHOR_API_URL ?? "http://localhost:8000";

interface RunState {
  status: "idle" | "uploading" | "running" | "done" | "error";
  report?: QualityReport;
  error?: string;
}

export function App() {
  const [apiKey, setApiKey] = useState("");
  const [useEncryption, setUseEncryption] = useState(true);
  const [run, setRun] = useState<RunState>({ status: "idle" });

  const client = useMemo(
    () => new AnchorClient({ baseUrl: API_BASE_URL, apiKey }),
    [apiKey]
  );

  const handleCheck = useCallback(async () => {
    if (!apiKey) {
      setRun({ status: "error", error: "Enter your X-Anchor-API-Key first." });
      return;
    }
    setRun({ status: "uploading" });
    try {
      const fileBytes = await getCurrentDocumentBytes();
      const filename = getDocumentName();

      let documentId: string;
      if (useEncryption) {
        const pk = await client.getOrgPublicKey();
        const ref = await client.uploadDocumentEncrypted(
          fileBytes,
          pk.public_key_pem,
          filename
        );
        documentId = ref.document_id;
      } else {
        const file = new File([fileBytes], filename, {
          type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        });
        const ref = await client.uploadDocument(file);
        documentId = ref.document_id;
      }

      setRun({ status: "running" });
      const runRef = await client.createRun({ document_id: documentId, mode: "report" });
      const report = await client.getRun(runRef.run_id);
      setRun({ status: "done", report });
    } catch (err) {
      setRun({ status: "error", error: err instanceof Error ? err.message : String(err) });
    }
  }, [apiKey, client, useEncryption]);

  return (
    <div style={{ padding: 16, fontFamily: "Segoe UI, Arial, sans-serif" }}>
      <Subtitle1 block>Anchor Quality Gate</Subtitle1>
      <Caption1 block style={{ marginBottom: 16, color: "#555" }}>
        Cite-check, Bluebook validate, and formatting fixes for the document
        currently open in Word.
      </Caption1>

      <Card>
        <CardHeader header={<Subtitle2>Connection</Subtitle2>} />
        <div style={{ padding: "0 12px 12px" }}>
          <input
            type="password"
            placeholder="X-Anchor-API-Key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            style={{ width: "100%", padding: 6, marginBottom: 8 }}
          />
          <Switch
            checked={useEncryption}
            onChange={(_, data) => setUseEncryption(!!data.checked)}
            label="Encrypt before upload (envelope flow)"
          />
        </div>
      </Card>

      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <Button
          appearance="primary"
          disabled={run.status === "uploading" || run.status === "running"}
          onClick={handleCheck}
        >
          {run.status === "uploading" || run.status === "running"
            ? "Working..."
            : "Run Quality Gate"}
        </Button>
        {(run.status === "uploading" || run.status === "running") && <Spinner size="tiny" />}
      </div>

      {run.status === "error" && (
        <div style={{ marginTop: 16, color: "crimson" }}>
          <Body1>Error: {run.error}</Body1>
        </div>
      )}

      {run.report && (
        <>
          <Divider style={{ marginTop: 16 }} />
          <ReportSummary report={run.report} />
          <FindingsList findings={run.report.findings} />
        </>
      )}
    </div>
  );
}

function ReportSummary({ report }: { report: QualityReport }) {
  const counts = report.findings.reduce<Record<Severity, number>>(
    (acc, f) => {
      acc[f.severity] = (acc[f.severity] ?? 0) + 1;
      return acc;
    },
    { error: 0, warning: 0, info: 0 }
  );
  return (
    <div style={{ marginTop: 12 }}>
      <Subtitle2 block>Score: {Math.round(report.score)}/100</Subtitle2>
      <Caption1>
        {counts.error} errors · {counts.warning} warnings · {counts.info} info
      </Caption1>
    </div>
  );
}

function FindingsList({ findings }: { findings: Finding[] }) {
  if (findings.length === 0) {
    return (
      <Body1 block style={{ marginTop: 12, color: "#0a0" }}>
        No findings.
      </Body1>
    );
  }
  return (
    <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
      {findings.map((f) => (
        <Card key={f.id}>
          <div style={{ padding: 12 }}>
            <Text weight="semibold" style={{ color: severityColor(f.severity) }}>
              {f.severity.toUpperCase()} · {f.rule_id}
            </Text>
            <Body1 block style={{ marginTop: 4 }}>
              {f.message}
            </Body1>
            <Caption1 block style={{ marginTop: 4, color: "#666" }}>
              Segment {f.segment_id} · provenance {f.provenance}
              {f.suggestion?.auto_apply_safe ? " · auto-safe" : ""}
            </Caption1>
          </div>
        </Card>
      ))}
    </div>
  );
}

function severityColor(s: Severity): string {
  return s === "error" ? "#c00" : s === "warning" ? "#b8860b" : "#0066cc";
}

// --- Office.js helpers ---

async function getCurrentDocumentBytes(): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    Office.context.document.getFileAsync(
      Office.FileType.Compressed,
      { sliceSize: 65536 },
      (result) => {
        if (result.status !== Office.AsyncResultStatus.Succeeded) {
          reject(new Error(result.error?.message ?? "Failed to read document"));
          return;
        }
        const file = result.value;
        const sliceCount = file.sliceCount;
        const slices: Uint8Array[] = [];

        const readSlice = (idx: number) => {
          file.getSliceAsync(idx, (sliceResult) => {
            if (sliceResult.status !== Office.AsyncResultStatus.Succeeded) {
              file.closeAsync();
              reject(
                new Error(
                  sliceResult.error?.message ?? `Failed reading slice ${idx}`
                )
              );
              return;
            }
            slices.push(new Uint8Array(sliceResult.value.data));
            if (idx + 1 < sliceCount) {
              readSlice(idx + 1);
            } else {
              file.closeAsync();
              resolve(concatUint8(slices));
            }
          });
        };
        readSlice(0);
      }
    );
  });
}

function concatUint8(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const p of parts) {
    out.set(p, offset);
    offset += p.length;
  }
  return out;
}

function getDocumentName(): string {
  // Office.js doesn't expose the filename cleanly; the document URL
  // is the best we have. Fall back to a generic name when it's not
  // available (e.g. unsaved documents).
  const url = Office.context.document.url ?? "";
  const last = url.split(/[\\/]/).pop();
  return last && last.endsWith(".docx") ? last : "document.docx";
}
