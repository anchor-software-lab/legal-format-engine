# Anchor Quality Gate — Office Add-in

React + TypeScript + Office.js taskpane for Word (Windows, Mac, Web).

The add-in opens a sidebar in Word that lets the user upload the
current document to the Anchor SaaS API, run the quality gate, and
review findings with one-click "go to range" / "accept suggestion"
controls.

## Architecture

- **`manifest.xml`** — Office Add-in manifest. Sideloaded into Word via
  the standard Microsoft dev-cert flow.
- **`src/taskpane/`** — React 18 taskpane (Office.js + Fluent UI).
- **`src/api/`** — typed HTTP client over `fetch` against the SaaS
  REST API documented in `../../schemas/openapi.yaml`. The types in
  `api/types.ts` are hand-mirrored from
  `../../schemas/json-schema/*.schema.json`; a later v1.5 task swaps
  in `openapi-typescript-codegen` so the client + types regenerate
  whenever the schema changes.
- **`src/api/crypto.ts`** — browser-side envelope encryption using
  the WebCrypto SubtleCrypto API. Mirrors the server's
  `legal_api.envelope` primitives: AES-256-GCM for the document,
  RSA-OAEP(SHA-256) for the DEK.

## Development

```bash
pnpm install
pnpm dev                # vite dev server on https://localhost:3000
pnpm sideload           # sideload manifest.xml into Word desktop
```

(Requires Node 20+, pnpm 9+, and Microsoft's
`office-addin-dev-certs` for the localhost HTTPS cert.)

## Production build

```bash
pnpm build
# → dist/ contains the taskpane HTML+JS bundle ready to host on a CDN.
```

The deployed manifest points at the CDN URL; users (or IT admins)
install the add-in from their Microsoft 365 admin center.

## What's in here vs what's pending

Currently:
- Manifest, package.json, tsconfig, vite config.
- React taskpane with upload + run + findings table flows.
- Typed API client with envelope-encryption upload helper.

Pending v1.5:
- Office.js range-mapping so each `Finding` becomes a clickable jump
  into the Word document.
- "Apply suggestion" path that inserts the suggested edit as a
  Word tracked change.
- Office add-in commands (ribbon button → open taskpane).
- Auto-generated TS client from the OpenAPI.
