import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: Vite on :5173 proxies /api to the FastAPI server on :8765 (make dev).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8765" } },
  // The manifest feeds scripts/check-bundle.mjs (F18 budget).
  build: { manifest: true, sourcemap: false },
});
