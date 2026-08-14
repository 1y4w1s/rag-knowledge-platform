#!/usr/bin/env node
/**
 * ui-smoke.mjs — 索隐 UI 验收脚本（替代不可用的 chrome-mcp）
 *
 * 用法（在 frontend/scripts/ui-smoke/ 下）：
 *   npm install
 *   node ui-smoke.mjs --url http://localhost/          # 探针模式：验证登录表单 + API 链路
 *   $env:RUIGE_SMOKE_EMAIL="user" ; $env:RUIGE_SMOKE_PASSWORD="pass"
 *   node ui-smoke.mjs --url http://localhost/          # 登录模式：断言进入 dashboard + 九页导航
 *
 * 登录模式九页：/dashboard /evaluations /ask /knowledge-bases
 *   /settings/account /about（静态）+ /knowledge-bases/{id}
 *   /knowledge-bases/{id}/chat /knowledge-bases/{id}/graph（动态，取账号第一个知识库）
 *   每页断言 HTTP < 400 且无新增 pageerror/requestfailed，截图 page-{name}.png
 * 输出：out/ 目录下截图（home.png / after-login.png / page-*.png 等），exit 0=通过。
 * 凭据只从环境变量读取，不落盘不打印。
 */
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.join(__dirname, "out");

const CHROME_PATHS = [
  process.env.RUIGE_CHROME_PATH,
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
].filter(Boolean);

function findChrome() {
  return CHROME_PATHS.find((p) => fs.existsSync(p));
}

function arg(name, fallback = "") {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1] : fallback;
}

// ── 九页导航配置（登录模式）──────────────────────────────────────
// 静态页：不依赖任何资源 id 的主路由。
// 动态页：需要真实 kb id，登录后从列表 API 解析第一个知识库补全。
const STATIC_PAGES = [
  { name: "dashboard", path: "/dashboard" },
  { name: "evaluations", path: "/evaluations" },
  { name: "ask", path: "/ask" },
  { name: "knowledge-bases", path: "/knowledge-bases" },
  { name: "settings-account", path: "/settings/account" },
  { name: "about", path: "/about" },
];

const DYNAMIC_PAGE_TEMPLATES = [
  { name: "kb-detail", path: (id) => `/knowledge-bases/${id}` },
  { name: "kb-chat", path: (id) => `/knowledge-bases/${id}/chat` },
  { name: "kb-graph", path: (id) => `/knowledge-bases/${id}/graph` },
];

/** 登录后从列表 API 取当前账号第一个知识库 id（页面内 fetch 自带 token）。 */
async function firstKnowledgeBaseId(page) {
  return page.evaluate(async () => {
    const token = localStorage.getItem("zhian_access_token");
    if (!token) return null;
    // workspace：personal 账号传 "personal"，enterprise 账号传 org_id（后端强制要求该参数）
    let workspace = "personal";
    try {
      const user = JSON.parse(localStorage.getItem("zhian_user") ?? "{}");
      if (user?.account_type === "enterprise" && user?.org_id) {
        workspace = user.org_id;
      }
    } catch {
      /* 保持 personal 默认 */
    }
    try {
      const res = await fetch(
        `/api/v1/knowledge-bases?limit=1&workspace=${encodeURIComponent(workspace)}`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!res.ok) return null;
      const data = await res.json();
      const items = Array.isArray(data) ? data : data.items;
      return items && items.length > 0 ? items[0].id : null;
    } catch {
      return null;
    }
  });
}

/**
 * 导航到一页并断言：
 * - HTTP 状态 < 400
 * - 页面加载前后无新增 pageerror / requestfailed（非 /api/）
 * 截图输出 page-{name}.png，返回该页错误数。
 */
async function visitPage(page, base, urlPath, name, errors) {
  const before = errors.length;
  const resp = await page.goto(base + urlPath, {
    waitUntil: "networkidle",
    timeout: 60000,
  });
  await page.waitForTimeout(2000); // 等 SPA 懒加载 chunk + 首屏请求

  const pageErrors = errors.slice(before);
  const status = resp?.status() ?? 0;
  const flag = status >= 400 ? "  [HTTP 错误]" : pageErrors.length > 0 ? "  [页面错误]" : "";
  console.log(
    `[page] ${name.padEnd(18)} ${urlPath.padEnd(42)} HTTP ${status}${flag}`,
  );
  if (status >= 400) throw new Error(`${name} 返回 HTTP ${status}`);
  for (const e of pageErrors) console.warn(`   - ${e}`);
  await page.screenshot({
    path: path.join(OUT_DIR, `page-${name}.png`),
    fullPage: false,
  });
  return pageErrors.length;
}

async function main() {
  const url = arg("--url", "http://localhost/");
  const base = url.replace(/\/+$/, ""); // 去掉尾斜杠，供子页面拼路径
  const chromePath = findChrome();
  if (!chromePath) {
    console.error("[FAIL] 未找到本机 Chrome/Edge，请设置 RUIGE_CHROME_PATH");
    process.exit(1);
  }
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const email = process.env.RUIGE_SMOKE_EMAIL;
  const password = process.env.RUIGE_SMOKE_PASSWORD;
  const loginMode = Boolean(email && password);
  console.log(`[mode] ${loginMode ? "登录模式" : "探针模式"}  url=${url}`);

  const browser = await chromium.launch({ executablePath: chromePath, headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => {
    if (!r.url().includes("/api/")) errors.push(`requestfailed: ${r.url()} ${r.failure()?.errorText ?? ""}`);
  });

  try {
    // 1. 打开首页
    const resp = await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
    console.log(`[1] GET ${url} -> HTTP ${resp?.status() ?? "?"}`);
    if ((resp?.status() ?? 0) >= 400) throw new Error(`首页返回 HTTP ${resp?.status()}`);

    await page.waitForSelector('input#identifier', { timeout: 15000 });
    console.log("[2] 登录表单已渲染（input#identifier 可见）");
    await page.screenshot({ path: path.join(OUT_DIR, "home.png"), fullPage: false });

    // 2. 表单交互
    await page.fill('input#identifier', loginMode ? email : "probe@smoke.local");
    await page.fill('input#password', loginMode ? password : "probe-password-123");
    console.log("[3] 已填写凭据，点击登录");
    await Promise.all([
      page.click('button[type="submit"]'),
      page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {}),
    ]);

    // 3. 断言
    if (loginMode) {
      // 登录模式：等待 URL 离开 /login（进入 dashboard 或 redirect 目标）
      await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 20000 });
      await page.waitForTimeout(1500); // 等 dashboard 首屏
      await page.screenshot({ path: path.join(OUT_DIR, "after-login.png"), fullPage: false });
      console.log(`[4] 登录成功，当前页面: ${page.url()}`);

      // 4. 九页导航：6 静态主路由 + 3 KB 动态页（需真实 kb id）
      const kbId = await firstKnowledgeBaseId(page);
      const pages = [...STATIC_PAGES];
      if (kbId) {
        for (const tpl of DYNAMIC_PAGE_TEMPLATES) {
          pages.push({ name: tpl.name, path: tpl.path(kbId) });
        }
      } else {
        console.warn("[warn] 当前账号无知识库，跳过 kb-detail / kb-chat / kb-graph 三页");
      }

      let pageFailures = 0;
      for (const p of pages) {
        pageFailures += await visitPage(page, base, p.path, p.name, errors);
      }
      const dynamicCount = pages.length - STATIC_PAGES.length;
      console.log(
        `[5] 九页导航完成：${pages.length} 页（静态 ${STATIC_PAGES.length} + 动态 ${dynamicCount}），截图见 ${OUT_DIR}`,
      );
      if (pageFailures > 0) {
        throw new Error(`${pageFailures} 个页面存在 pageerror/requestfailed`);
      }
    } else {
      // 探针模式：期望出现 [role="alert"] 错误提示（证明 API 链路通）
      const alert = await page
        .waitForSelector('[role="alert"]', { timeout: 20000 })
        .catch(() => null);
      if (!alert) throw new Error("未出现错误提示（登录 API 链路未通或断言逻辑失效）");
      const text = (await alert.textContent()) ?? "";
      console.log(`[4] 探针登录返回错误提示: ${text.trim()}`);
      await page.screenshot({ path: path.join(OUT_DIR, "probe-error.png"), fullPage: false });
    }

    if (errors.length > 0) {
      console.warn(`[warn] 页面异常 ${errors.length} 条:`);
      for (const e of errors) console.warn(`  - ${e}`);
    }
    console.log("[PASS] UI smoke 验收通过");
    console.log(`截图目录: ${OUT_DIR}`);
  } catch (err) {
    await page.screenshot({ path: path.join(OUT_DIR, "failure.png"), fullPage: false }).catch(() => {});
    console.error(`[FAIL] ${err.message}`);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
