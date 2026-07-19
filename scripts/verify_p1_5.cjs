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

  // admin 登录（canEdit + canDelete 都为 true）
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 30000 });
  await page.evaluate(() => localStorage.clear());
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector('input[type="text"], input[type="email"]', { timeout: 10000 });
  await page.type('input[type="text"], input[type="email"]', "demo_admin", { delay: 5 });
  await page.type('input[type="password"]', "password123", { delay: 5 });
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle2", timeout: 15000 }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
  await new Promise((r) => setTimeout(r, 800));

  await page.goto(`${BASE}/knowledge-bases`, { waitUntil: "networkidle2", timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1500));
  await page.screenshot({
    path: path.join(OUT, "verify_p1_5_kb_list_admin.png"),
    clip: { x: 0, y: 0, width: 1440, height: 800 },
  });
  console.log("✓ admin /knowledge-bases → verify_p1_5_kb_list_admin.png");
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
