const puppeteer = require("puppeteer-core");
const path = require("node:path");
const fs = require("node:fs");

const OUT = path.join(__dirname, "..", "docs", "frontend-rework", "screenshots");
fs.mkdirSync(OUT, { recursive: true });

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://localhost:5173";

async function login(page, identifier) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 20000 });
  await page.waitForSelector("#identifier", { timeout: 15000 });
  await page.type("#identifier", identifier, { delay: 5 });
  await page.type('input[type="password"]', "password123", { delay: 5 });
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle2", timeout: 20000 }),
    page.click('button[type="submit"]'),
  ]);
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
    page.on("pageerror", (err) => console.log("  [pageerror]", err.message));

    // ====== admin 团队视角 ======
    console.log("== admin login ==");
    await login(page, "demo_admin");
    await page.evaluate(() => {
      const user = JSON.parse(localStorage.getItem("zhian_user") || "null");
      if (user && user.org_id) {
        localStorage.setItem("zhian-workspace", JSON.stringify({ id: user.org_id }));
      }
    });
    await page.reload({ waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1500));

    // 找一个有文档的 KB
    await page.goto(`${BASE}/knowledge-bases`, { waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1500));

    const kbWithDocs = await page.evaluate(() => {
      // 找包含"X 文档"或非 0 文档数的卡片链接
      const cards = document.querySelectorAll("a[href^='/knowledge-bases/']");
      for (const card of cards) {
        const text = card.textContent || "";
        if (!/0\s*篇文档|空库/.test(text)) {
          const m = card.getAttribute("href").match(/\/knowledge-bases\/([^/?]+)/);
          if (m) return m[1];
        }
      }
      // 兜底：第一个 KB
      if (cards.length > 0) {
        const m = cards[0].getAttribute("href").match(/\/knowledge-bases\/([^/?]+)/);
        return m ? m[1] : null;
      }
      return null;
    });
    console.log("  ✓ KB with docs:", kbWithDocs);

    if (!kbWithDocs) {
      console.log("  ✗ no KB");
      process.exit(1);
    }

    // 进入 KB 详情，拿到 docId
    await page.goto(`${BASE}/knowledge-bases/${kbWithDocs}`, { waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 2000));

    const docId = await page.evaluate(() => {
      const link = document.querySelector('a[href*="/documents/"]');
      if (!link) return null;
      const m = link.getAttribute("href").match(/\/documents\/([^/?#]+)/);
      return m ? m[1] : null;
    });
    console.log("  ✓ first docId:", docId);

    if (!docId) {
      console.log("  ✗ no doc");
      process.exit(1);
    }

    // 拍：light admin 预览页
    await page.goto(`${BASE}/knowledge-bases/${kbWithDocs}/documents/${docId}`, {
      waitUntil: "networkidle2",
      timeout: 20000,
    });
    await new Promise((r) => setTimeout(r, 2500));
    await page.screenshot({
      path: path.join(OUT, "review_preview_light_admin.png"),
      fullPage: false,
    });
    console.log("  ✓ light admin");

    // dark admin
    await page.evaluate(() => {
      localStorage.setItem("zhian-theme", JSON.stringify({ theme: "dark" }));
    });
    await page.reload({ waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 2500));
    await page.screenshot({
      path: path.join(OUT, "review_preview_dark_admin.png"),
      fullPage: false,
    });
    console.log("  ✓ dark admin");

    // ====== member personal 视角 ======
    await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 20000 });
    await page.evaluate(() => localStorage.clear());
    await page.reload({ waitUntil: "networkidle2", timeout: 20000 });
    await login(page, "demo_member");
    await new Promise((r) => setTimeout(r, 1200));

    // member 在 personal 视角找一个有可预览 doc 的 KB
    await page.goto(`${BASE}/knowledge-bases`, { waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1500));

    const memberKb = await page.evaluate(() => {
      const cards = document.querySelectorAll("a[href^='/knowledge-bases/']");
      for (const card of cards) {
        const text = card.textContent || "";
        if (!/0\s*篇文档|空库/.test(text)) {
          const m = card.getAttribute("href").match(/\/knowledge-bases\/([^/?]+)/);
          if (m) return m[1];
        }
      }
      if (cards.length > 0) {
        const m = cards[0].getAttribute("href").match(/\/knowledge-bases\/([^/?]+)/);
        return m ? m[1] : null;
      }
      return null;
    });
    console.log("  ✓ member KB with docs:", memberKb);

    if (memberKb) {
      await page.goto(`${BASE}/knowledge-bases/${memberKb}`, { waitUntil: "networkidle2", timeout: 20000 });
      await new Promise((r) => setTimeout(r, 2000));

      const memberDoc = await page.evaluate(() => {
        const link = document.querySelector('a[href*="/documents/"]');
        if (!link) return null;
        const m = link.getAttribute("href").match(/\/documents\/([^/?#]+)/);
        return m ? m[1] : null;
      });
      console.log("  ✓ member docId:", memberDoc);

      if (memberDoc) {
        await page.goto(`${BASE}/knowledge-bases/${memberKb}/documents/${memberDoc}`, {
          waitUntil: "networkidle2",
          timeout: 20000,
        });
        await new Promise((r) => setTimeout(r, 2500));
        await page.screenshot({
          path: path.join(OUT, "review_preview_light_member.png"),
          fullPage: false,
        });
        console.log("  ✓ light member");
      }
    }

    console.log("== DONE ==");
  } finally {
    await browser.close();
  }
})();
