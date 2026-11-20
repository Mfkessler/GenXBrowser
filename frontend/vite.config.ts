import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vueDevTools from "vite-plugin-vue-devtools";
import tailwindcss from "@tailwindcss/vite";

// Build proxy config dynamically: if VITE_API_BASE_URL is a sub-path like
// "/dev/genxbrowser", we also need to proxy requests under that prefix
// (e.g. /dev/genxbrowser/api → http://backend:5000/api).
const apiBase = process.env.VITE_API_BASE_URL || "";
const backendTarget = process.env.GENX_DEV_BACKEND_URL || "http://backend:5000";

function buildProxy() {
  const routes: Record<string, object> = {
    "/api": { target: backendTarget, changeOrigin: true },
    "/health": { target: backendTarget, changeOrigin: true },
  };
  // When running behind a sub-path, add rewriting proxy entries
  if (apiBase && apiBase !== "/" && apiBase !== "") {
    const prefix = apiBase.replace(/\/$/, ""); // strip trailing slash
    routes[`${prefix}/api`] = {
      target: backendTarget,
      changeOrigin: true,
      rewrite: (path: string) => path.replace(new RegExp(`^${prefix}`), ""),
    };
    routes[`${prefix}/health`] = {
      target: backendTarget,
      changeOrigin: true,
      rewrite: (path: string) => path.replace(new RegExp(`^${prefix}`), ""),
    };
  }
  return routes;
}

// Parse allowed hosts from environment variable (comma-separated)
function getAllowedHosts(): string[] {
  const defaultHosts = ["localhost", "127.0.0.1"];
  const envHosts = process.env.VITE_ALLOWED_HOSTS;
  
  if (envHosts) {
    const additional = envHosts.split(",").map(h => h.trim()).filter(h => h);
    return [...defaultHosts, ...additional];
  }
  
  return defaultHosts;
}

// https://vite.dev/config/
export default defineConfig({
  base: process.env.VITE_BASE_URL || "/",
  plugins: [vue(), vueDevTools(), tailwindcss()],
  server: { 
    host: "0.0.0.0",
    allowedHosts: getAllowedHosts(),
    // Proxy API requests to backend container (for Docker dev environment)
    proxy: buildProxy(),
    // HMR configuration for Docker
    watch: {
      usePolling: true, // Required for Docker volumes
    },
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  optimizeDeps: {
    include: ["plotly.js-dist-min"],
  },
  build: {
    chunkSizeWarningLimit: 5000,
    commonjsOptions: {
      include: [/plotly\.js-dist-min/, /node_modules/],
    },
  },
});
