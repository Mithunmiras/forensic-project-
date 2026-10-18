/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// Dev server: the browser talks to the Vite origin and /api is proxied to the FastAPI backend,
// so no CORS setup is needed. Point it elsewhere with VITE_PROXY_TARGET (e.g. when port 8000 is taken).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const target = env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": target, "/health": target, "/docs": target, "/openapi.json": target },
    },
    build: { sourcemap: false, chunkSizeWarningLimit: 900 },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: false,
    },
  };
});
