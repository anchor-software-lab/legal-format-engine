import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Office Add-ins must be served over HTTPS. In dev we rely on
// office-addin-dev-certs to mint a cert under
// ~/.office-addin-dev-certs/; the manifest.xml SourceLocation points at
// https://localhost:3000/taskpane.html.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    https: false, // flip to true + cert config when running locally
    strictPort: true,
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      input: {
        taskpane: resolve(__dirname, "src/taskpane/index.html"),
      },
    },
  },
});
