import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiProxyTarget =
  process.env.VITE_DEV_API_PROXY ?? "http://127.0.0.1:8003";

export default defineConfig({
  plugins: [react()],
  server: {
    strictPort: true,
    allowedHosts: [
      "heimdallur.dsna.codes",
      "localhost",
      "127.0.0.1",
      "192.168.0.3"
    ],
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true
      }
    }
  }
});
