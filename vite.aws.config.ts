import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  root: "aws-ui",
  publicDir: "../public",
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/v1": "http://127.0.0.1:8000",
    },
  },
  build: {
    emptyOutDir: true,
    outDir: "../dist-aws-ui",
    sourcemap: true,
  },
});
