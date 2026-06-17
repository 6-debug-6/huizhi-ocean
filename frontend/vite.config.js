import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";
import http from "http";

// 限制代理连接池大小，防止并发请求压垮后端 SQLite
const agent = new http.Agent({
  keepAlive: true,
  maxSockets: 8,       // 最多8个并发连接
  maxFreeSockets: 4,   // 空闲连接保留4个
  timeout: 30000,      // 30秒空闲超时
});

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        agent,  // 使用有限连接池
        configure: (proxy) => {
          proxy.on("error", (err, req, res) => {
            console.error("[proxy error]", err.message);
            if (res && !res.headersSent) {
              res.writeHead(502, { "Content-Type": "application/json" });
              res.end(JSON.stringify({ detail: "代理请求失败，请稍后重试" }));
            }
          });
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
      // 静态文件也通过代理访问后端
      "/uploads": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
