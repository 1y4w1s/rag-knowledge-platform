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
  await page.type('input[type="text"], input[type="email"]', "demo_admin", { delay: 5 });
  await page.type('input[type="password"]', "password123", { delay: 5 });
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle2", timeout: 15000 }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
  await new Promise((r) => setTimeout(r, 1000));

  await page.goto(`${BASE}/settings/account`, { waitUntil: "networkidle2", timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1500));

  // 截顶部 800px viewport 区域（包含 SectionTitle + 账号信息卡片）
  await page.screenshot({
    path: path.join(OUT, "verify_nickname_card.png"),
    clip: { x: 0, y: 0, width: 1440, height: 800 },
  });
  console.log("✓ 卡片特写 → verify_nickname_card.png");

  // 测试输入框：填入新昵称
  await page.click('input#account-nickname', { clickCount: 3 });
  await page.keyboard.press("Backspace");
  await page.type('input#account-nickname', "演示·管理员", { delay: 5 });
  await new Promise((r) => setTimeout(r, 500));
  await page.screenshot({
    path: path.join(OUT, "verify_nickname_filled.png"),
    clip: { x: 0, y: 0, width: 1440, height: 800 },
  });
  console.log("✓ 输入新昵称后 → verify_nickname_filled.png");

  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
