import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development /api is proxied to Django. In production CloudFront routes /api/* to the load balancer,
// so the browser always talks to one origin and no CORS is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000" },
  },
});
