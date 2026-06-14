import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // 连接池限制：http-proxy 默认无限制，大量并发会压垮后端 SQLite
        // 限制并发连接数，避免连接泄漏导致后端过载
        configure: (proxy) => {
          proxy.on("error", (err, req, res) => {
            // 代理错误不崩溃，记录后返回 502
            console.error("[proxy error]", err.message);
            if (res && !res.headersSent) {
              res.writeHead(502, { "Content-Type": "application/json" });
              res.end(JSON.stringify({ detail: "代理请求失败，请稍后重试" }));
            }
          });
          // 请求超时限制
          proxy.on("proxyReq", (proxyReq, req, res) => {
            req.setTimeout(25000, () => {
              proxyReq.destroy();
              if (!res.headersSent) {
                res.writeHead(504, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ detail: "请求超时" }));
              }
            });
          });
        },
      },
    },
  },
});
