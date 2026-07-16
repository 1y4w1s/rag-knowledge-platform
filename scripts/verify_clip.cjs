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
  await page.setViewport({ width: 1280, height: 800, deviceScaleFactor: 1 });

  // 登录
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 30000 });
  await page.evaluate(() => {
    localStorage.removeItem("zhian_access_token");
    localStorage.removeItem("zhian_user");
  });
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector('input[type="text"], input[type="email"]', { timeout: 10000 });
  await page.type('input[type="text"], input[type="email"]', "demo_admin", { delay: 5 });
  await page.type('input[type="password"]', "password123", { delay: 5 });
  await Promise.all([
    page.waitForNavigation({ waitUntil: "networkidle2", timeout: 15000 }).catch(() => null),
    page.click('button[type="submit"]'),
  ]);
  await new Promise((r) => setTimeout(r, 800));

  // 跳到资料库列表（左侧能看到团队设置图标）
  await page.goto(`${BASE}/knowledge-bases`, { waitUntil: "networkidle2", timeout: 20000 });
  await new Promise((r) => setTimeout(r, 800));

  // 切到团队工作区（demo_admin 是 enterprise 用户 + org admin）
  await page.evaluate(() => {
    const user = JSON.parse(localStorage.getItem("zhian_user") || "null");
    if (user && user.org_id) {
      localStorage.setItem("zhian-workspace", user.org_id);
    }
  });
  await page.reload({ waitUntil: "networkidle2", timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1200));

  // 顶栏特写（1280x80）
  await page.screenshot({
    path: path.join(OUT, "verify_topbar_chip.png"),
    clip: { x: 0, y: 0, width: 1280, height: 80 },
  });
  // 侧边栏特写（左侧 280x800）
  await page.screenshot({
    path: path.join(OUT, "verify_sidebar_team_settings.png"),
    clip: { x: 0, y: 0, width: 280, height: 800 },
  });

  console.log("✓ 顶栏特写 →", path.join(OUT, "verify_topbar_chip.png"));
  console.log("✓ 侧边栏特写 →", path.join(OUT, "verify_sidebar_team_settings.png"));
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
