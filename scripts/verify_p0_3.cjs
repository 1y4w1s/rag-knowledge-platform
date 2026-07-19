const puppeteer = require("puppeteer-core");
const path = require("path");

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://localhost:5173";
const OUT = path.resolve(__dirname, "../docs/frontend-rework/screenshots");

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });

  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 30000 });
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector('input[type="text"], input[type="email"]', { timeout: 10000 });
  await page.type('input[type="text"], input[type="email"]', "demo_member", { delay: 5 });
  await page.type('input[type="password"]', "password123", { delay: 5 });
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle2", timeout: 15000 }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
  await new Promise((r) => setTimeout(r, 1200));

  await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle2", timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({
    path: path.join(OUT, "verify_p0_3_member_dashboard.png"),
    fullPage: true,
  });
  console.log("✓ member /dashboard (0 文档态) → verify_p0_3_member_dashboard.png");
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
