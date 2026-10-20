import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Dev only (`npm run dev`): forward API calls to `python dev_server.py`.
  // Production builds are served by Vercel and ignore this.
  server: {
    proxy: { "/api": "http://127.0.0.1:3001" },
  },
});
