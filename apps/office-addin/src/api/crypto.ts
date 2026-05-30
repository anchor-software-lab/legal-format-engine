// Browser-side envelope encryption using WebCrypto / SubtleCrypto.
//
// Mirrors `legal_api.envelope` server-side:
//   - AES-256-GCM with a fresh 96-bit nonce per document.
//   - RSA-OAEP(SHA-256, MGF1-SHA256) wraps the DEK with the org's
//     public key.
//
// The server holds only the public key; the corresponding private key
// stays on the customer's machine (today: provided by the user; v1.5:
// imported from a keystore or a session-unwrap webhook).

export interface EncryptedPayload {
  ciphertext: Uint8Array;
  nonce: Uint8Array;
  wrappedDek: Uint8Array;
  /** SHA-256 of the plaintext, hex-encoded; sent for integrity check. */
  sha256Hex: string;
}

const DEK_BYTES = 32;
const NONCE_BYTES = 12;

export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Generate a fresh 256-bit AES-GCM key, exported as raw bytes. */
async function generateDek(): Promise<Uint8Array> {
  const key = await crypto.subtle.generateKey(
    { name: "AES-GCM", length: 256 },
    true,
    ["encrypt", "decrypt"]
  );
  const raw = await crypto.subtle.exportKey("raw", key);
  return new Uint8Array(raw);
}

/** AES-256-GCM encrypt with a fresh 12-byte nonce. */
async function encryptDocument(
  plaintext: Uint8Array,
  dek: Uint8Array
): Promise<{ ciphertext: Uint8Array; nonce: Uint8Array }> {
  if (dek.length !== DEK_BYTES) {
    throw new Error(`DEK must be ${DEK_BYTES} bytes`);
  }
  const key = await crypto.subtle.importKey(
    "raw",
    dek,
    { name: "AES-GCM" },
    false,
    ["encrypt"]
  );
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_BYTES));
  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce },
    key,
    plaintext
  );
  return { ciphertext: new Uint8Array(ciphertext), nonce };
}

/** RSA-OAEP(SHA-256) wrap a DEK with a PEM-encoded SPKI public key. */
async function wrapDek(
  dek: Uint8Array,
  publicKeyPem: string
): Promise<Uint8Array> {
  const key = await importRsaPublicKey(publicKeyPem);
  const wrapped = await crypto.subtle.encrypt(
    { name: "RSA-OAEP" },
    key,
    dek
  );
  return new Uint8Array(wrapped);
}

async function importRsaPublicKey(pem: string): Promise<CryptoKey> {
  // Strip PEM header/footer and base64-decode the body.
  const b64 = pem
    .replace(/-----BEGIN [^-]+-----/, "")
    .replace(/-----END [^-]+-----/, "")
    .replace(/\s+/g, "");
  const der = base64ToBytes(b64);
  return crypto.subtle.importKey(
    "spki",
    der,
    { name: "RSA-OAEP", hash: "SHA-256" },
    false,
    ["encrypt"]
  );
}

export async function encryptForUpload(
  plaintext: Uint8Array,
  publicKeyPem: string
): Promise<EncryptedPayload> {
  const dek = await generateDek();
  const { ciphertext, nonce } = await encryptDocument(plaintext, dek);
  const wrappedDek = await wrapDek(dek, publicKeyPem);
  const sha = await sha256Hex(plaintext);
  // Zero the DEK reference promptly; no actual memory guarantee in JS.
  dek.fill(0);
  return { ciphertext, nonce, wrappedDek, sha256Hex: sha };
}

// --- base64 helpers ---

export function bytesToBase64(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.byteLength; i++) {
    bin += String.fromCharCode(bytes[i]);
  }
  return btoa(bin);
}

export function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) {
    out[i] = bin.charCodeAt(i);
  }
  return out;
}
