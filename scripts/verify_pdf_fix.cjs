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
    page.on("console", (msg) => {
      const txt = msg.text();
      if (msg.type() === "error" && /preview|pdf|blob|frame|502/.test(txt)) {
        console.log("  [console]", txt.slice(0, 200));
      }
    });
    page.on("response", (res) => {
      const url = res.url();
      if (url.includes("/preview")) {
        console.log(`  [HTTP] ${res.status()} ${res.headers()["x-frame-options"] ?? ""} ${url.slice(0, 100)}`);
      }
    });

    await login(page, "demo_admin");
    await page.evaluate(() => {
      const user = JSON.parse(localStorage.getItem("zhian_user") || "null");
      if (user && user.org_id) {
        localStorage.setItem("zhian-workspace", JSON.stringify({ id: user.org_id }));
      }
    });
    await page.reload({ waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1500));

    // 团队视角下拉所有 KB，找含 PDF doc 的
    const found = await page.evaluate(async () => {
      const list = await fetch("/api/v1/knowledge-bases?limit=50", { credentials: "include" });
      const data = await list.json();
      const kbs = data.items || [];
      for (const kb of kbs) {
        const docs = await fetch(`/api/v1/knowledge-bases/${kb.id}/documents?limit=10`, { credentials: "include" });
        const ddata = await docs.json();
        for (const d of ddata.items || []) {
          if ((d.filename || "").toLowerCase().endsWith(".pdf") && d.status === "completed") {
            return { kbId: kb.id, docId: d.id, filename: d.filename };
          }
        }
      }
      return null;
    });
    console.log("  ✓ found PDF:", found);

    if (!found) {
      console.log("  ✗ no PDF found in team workspace");
      process.exit(1);
    }

    await page.goto(`${BASE}/knowledge-bases/${found.kbId}/documents/${found.docId}`, {
      waitUntil: "networkidle2",
      timeout: 30000,
    });
    await new Promise((r) => setTimeout(r, 5000));
    await page.screenshot({
      path: path.join(OUT, "verify_pdf_preview_after_fix.png"),
      fullPage: false,
    });
    console.log("  ✓ PDF shot saved");

    // 暗色也拍
    await page.evaluate(() => {
      localStorage.setItem("zhian-theme", JSON.stringify({ theme: "dark" }));
    });
    await page.reload({ waitUntil: "networkidle2", timeout: 30000 });
    await new Promise((r) => setTimeout(r, 5000));
    await page.screenshot({
      path: path.join(OUT, "verify_pdf_preview_after_fix_dark.png"),
      fullPage: false,
    });
    console.log("  ✓ PDF dark shot saved");

    console.log("== DONE ==");
  } finally {
    await browser.close();
  }
})();
