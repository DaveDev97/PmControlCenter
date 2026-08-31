import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// Dev server proxies /api to the FastAPI backend on port 8000.
export default defineConfig({
    plugins: [react()],
    base: "./", // relative paths so the build works when loaded from file:// in Electron
    server: {
        port: 3000,
        host: true, // Allow external access
        allowedHosts: [
            "ui-30711998-f485-4130-9c40-66ed5a808ed0.secai.chat", // AURA public URL
            ".secai.chat", // Allow all secai.chat subdomains
        ],
        proxy: {
            "/api": {
                target: "http://127.0.0.1:8000",
                changeOrigin: true,
            },
        },
    },
});
