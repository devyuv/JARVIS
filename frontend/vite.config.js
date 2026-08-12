import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/JARVIS/",
  server: {
    port: 5173,
  },
});
