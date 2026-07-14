import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// 开发模式需放宽 CSP 以兼容 Vite 的 react-refresh / HMR 内联脚本与 WebSocket，
// 否则 script-src 'self' 会拦截 react-refresh preamble，导致 React dispatcher 未初始化、
// 出现 "Invalid hook call / Cannot read properties of null (reading 'useState')"。
// 生产模式保持严格同源策略，保证 Lighthouse D8 安全分。
const DEV_CSP =
  "default-src 'self'; img-src 'self' data: https:; font-src 'self' https: data:; " +
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
  "script-src 'self' 'unsafe-inline'; connect-src 'self' ws:; frame-src 'self'";
const PROD_CSP =
  "default-src 'self'; img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com; " +
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
  "script-src 'self'; connect-src 'self'; frame-src 'self'";

export default defineConfig(({ command }) => {
  const isDev = command === "serve";
  const csp = isDev ? DEV_CSP : PROD_CSP;

  return {
    plugins: [
      react(),
      {
        name: "inject-csp-meta",
        // index.html 中的静态 CSP meta 已移除，改由本插件按模式注入，保证单一来源
        transformIndexHtml: {
          enforce: "pre",
          transform(html) {
            const metaTag = `<meta http-equiv="Content-Security-Policy" content="${csp}">`;
            if (/<meta http-equiv="Content-Security-Policy"/.test(html)) {
              return html.replace(
                /<meta http-equiv="Content-Security-Policy"[^>]*>/,
                metaTag,
              );
            }
            return {
              html,
              tags: [
                {
                  tag: "meta",
                  attrs: {
                    "http-equiv": "Content-Security-Policy",
                    content: csp,
                  },
                  injectTo: "head",
                },
              ],
            };
          },
        },
      },
    ],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
      setupFiles: ["./src/test-setup.ts"],
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
    build: {
      target: "es2020",
      cssCodeSplit: true,
      // 现代浏览器原生支持 modulepreload；关闭 polyfill 避免注入内联脚本（与 CSP script-src 'self' 冲突）
      modulePreload: { polyfill: false },
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules")) {
              if (
                id.includes("react-router") ||
                id.includes("@remix-run") ||
                id.includes("react-dom") ||
                id.includes("/react/") ||
                id.includes("scheduler")
              ) {
                return "react-vendor";
              }
              return "vendor";
            }
          },
        },
      },
    },
  };
});
