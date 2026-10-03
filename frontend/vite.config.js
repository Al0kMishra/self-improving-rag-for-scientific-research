import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": process.env.VITE_API_PROXY || `http://localhost:${process.env.BACKEND_PORT || 8000}`,
    },
  },
});
