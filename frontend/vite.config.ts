import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development Vite serves the React app on :5173 and forwards API calls
// to Flask on :5000. In production Flask serves the built files from dist/.
const api = "http://127.0.0.1:5000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": api, "/uploads": api, "/__test__": api },
  },
});
