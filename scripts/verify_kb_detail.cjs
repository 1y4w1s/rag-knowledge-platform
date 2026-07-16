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

    console.log("== login demo_admin ==");
    await login(page, "demo_admin");
    console.log("  ✓ logged in");

    await page.evaluate(() => {
      const user = JSON.parse(localStorage.getItem("zhian_user") || "null");
      if (user && user.org_id) {
        localStorage.setItem("zhian-workspace", JSON.stringify({ id: user.org_id }));
      }
    });
    await page.reload({ waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1500));
    console.log("  ✓ team workspace");

    await page.goto(`${BASE}/knowledge-bases`, { waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1500));

    const kbId = await page.evaluate(() => {
      const card = document.querySelector("a[href^='/knowledge-bases/']");
      if (!card) return null;
      const m = card.getAttribute("href").match(/\/knowledge-bases\/([^/?]+)/);
      return m ? m[1] : null;
    });
    console.log("  ✓ first KB id:", kbId);

    if (!kbId) {
      console.log("  ✗ no KB found");
      process.exit(1);
    }

    // 亮色 admin
    await page.goto(`${BASE}/knowledge-bases/${kbId}`, { waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1800));
    await page.screenshot({
      path: path.join(OUT, "verify_kb_detail_light_admin.png"),
      fullPage: false,
    });
    console.log("  ✓ light admin shot");

    // 暗色 admin
    await page.evaluate(() => {
      localStorage.setItem("zhian-theme", JSON.stringify({ theme: "dark" }));
    });
    await page.reload({ waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1800));
    await page.screenshot({
      path: path.join(OUT, "verify_kb_detail_dark_admin.png"),
      fullPage: false,
    });
    console.log("  ✓ dark admin shot");

    // 切 member
    await page.evaluate(() => {
      localStorage.clear();
    });
    await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 20000 });
    await login(page, "demo_member");
    await new Promise((r) => setTimeout(r, 1200));

    await page.evaluate(() => {
      const user = JSON.parse(localStorage.getItem("zhian_user") || "null");
      if (user) {
        localStorage.setItem("zhian-workspace", JSON.stringify({ id: "personal" }));
      }
    });
    await page.reload({ waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1500));

    await page.goto(`${BASE}/knowledge-bases`, { waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1500));

    const memberKbId = await page.evaluate(() => {
      const card = document.querySelector("a[href^='/knowledge-bases/']");
      if (!card) return null;
      const m = card.getAttribute("href").match(/\/knowledge-bases\/([^/?]+)/);
      return m ? m[1] : null;
    });
    console.log("  ✓ first member KB id:", memberKbId);

    if (memberKbId) {
      await page.goto(`${BASE}/knowledge-bases/${memberKbId}`, { waitUntil: "networkidle2", timeout: 20000 });
      await new Promise((r) => setTimeout(r, 1500));
      await page.screenshot({
        path: path.join(OUT, "verify_kb_detail_light_member.png"),
        fullPage: false,
      });
      console.log("  ✓ light member shot");
    }

    console.log("== DONE ==");
  } finally {
    await browser.close();
  }
})();
