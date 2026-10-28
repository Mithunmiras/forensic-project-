import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` serves the UI on :5173 and proxies the API to the FastAPI server on :8000.
export default defineConfig({
  plugins: [react()],
  build: { chunkSizeWarningLimit: 900 },
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
});
