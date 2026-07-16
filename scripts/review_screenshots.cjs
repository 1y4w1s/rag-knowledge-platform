/**
 * 苛刻设计评审：登录两个 demo 账号，对 5 个关键页面各拍 2 张（亮/暗）截图，
 * 并 dump 关键元素位置/颜色，便于后续代码层评审。
 */
const puppeteer = require("puppeteer-core");
const fs = require("fs");
const path = require("path");

const OUT = path.resolve(__dirname, "../docs/frontend-rework/screenshots");
fs.mkdirSync(OUT, { recursive: true });

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://localhost:5173";
const ACCOUNTS = [
  { tag: "admin", identifier: "demo_admin" },
  { tag: "member", identifier: "demo_member" },
];
const PAGES = [
  { key: "01-dashboard", path: "/dashboard" },
  { key: "02-kb-list", path: "/knowledge-bases" },
  { key: "03-org-departments", path: "/organization/departments" },
  { key: "04-org-members", path: "/organization/members" },
  { key: "05-account-settings", path: "/settings/account" },
];

async function login(page, identifier) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 30000 });
  // 清掉旧 session
  await page.evaluate(() => {
    localStorage.removeItem("zhian_access_token");
    localStorage.removeItem("zhian_user");
  });
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector('input[name="identifier"], input[type="text"], input[type="email"]', { timeout: 10000 });
  await page.type('input[name="identifier"], input[type="text"], input[type="email"]', identifier, { delay: 5 });
  await page.type('input[type="password"]', "password123", { delay: 5 });
  // 提交
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle2", timeout: 15000 }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
  await new Promise((r) => setTimeout(r, 800));
}

async function dumpTheme(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    return root.getAttribute("data-theme") || "light";
  });
}

async function dumpGeometry(page) {
  return page.evaluate(() => {
    const get = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: Math.round(r.top + window.scrollY), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height) };
    };
    const colorOf = (sel, prop) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      return getComputedStyle(el)[prop];
    };
    return {
      url: location.pathname,
      docH: document.documentElement.scrollHeight,
      theme: document.documentElement.getAttribute("data-theme"),
      bodyBg: colorOf("body", "backgroundColor"),
      bodyColor: colorOf("body", "color"),
      sectionCount: document.querySelectorAll("section[aria-label]").length,
      h1: get("h1"),
      h2List: Array.from(document.querySelectorAll("h2")).slice(0, 6).map((e) => e.textContent?.trim() || ""),
      h3List: Array.from(document.querySelectorAll("h3")).slice(0, 6).map((e) => e.textContent?.trim() || ""),
      containers: Array.from(document.querySelectorAll(".max-w-\\[1180px\\]")).length,
      trackingWide: Array.from(document.querySelectorAll("[class*='tracking-wide']"))
        .slice(0, 6)
        .map((e) => ({ tag: e.tagName, cls: e.className.toString().slice(0, 80), text: (e.textContent || "").trim().slice(0, 30) })),
      hardcoded: Array.from(document.querySelectorAll("[class*='border-zinc-'], [class*='bg-zinc-'], [class*='text-zinc-'], [class*='text-slate-']"))
        .slice(0, 6)
        .map((e) => ({ tag: e.tagName, cls: e.className.toString().slice(0, 80) })),
    };
  });
}

async function shoot(browser, account, theme) {
  const page = await browser.newPage();
  page.setDefaultTimeout(15000);
  page.on("pageerror", (e) => console.error(`  [pageerror] ${e.message}`));
  page.on("console", (m) => {
    if (m.type() === "error") console.error(`  [console.error] ${m.text().slice(0, 200)}`);
  });

  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await login(page, account.identifier);

  // 切主题：通过顶栏的 sun-icon 按钮
  const currentTheme = await dumpTheme(page);
  if (currentTheme !== theme) {
    await page.click("button.sun-icon").catch(() => null);
    await new Promise((r) => setTimeout(r, 500));
  }

  for (const p of PAGES) {
    try {
      await page.goto(`${BASE}${p.path}`, { waitUntil: "networkidle2", timeout: 20000 });
      await new Promise((r) => setTimeout(r, 1200));
      const file = path.join(OUT, `${account.tag}_${theme}_${p.key}.png`);
      await page.screenshot({ path: file, fullPage: true });
      const geo = await dumpGeometry(page);
      fs.writeFileSync(file.replace(".png", ".json"), JSON.stringify(geo, null, 2));
      console.log(`  ✓ ${account.tag}/${theme} ${p.path}  →  ${path.basename(file)}`);
    } catch (e) {
      console.error(`  ✗ ${account.tag}/${theme} ${p.path}: ${e.message}`);
    }
  }
  await page.close();
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  for (const acc of ACCOUNTS) {
    for (const theme of ["light", "dark"]) {
      console.log(`\n=== ${acc.tag} / ${theme} ===`);
      await shoot(browser, acc, theme);
    }
  }
  await browser.close();
  console.log("\nDONE. 截图:", OUT);
})().catch((e) => {
  console.error("FATAL", e);
  process.exit(1);
});
