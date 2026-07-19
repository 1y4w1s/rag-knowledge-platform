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

  // 登录 demo_admin
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 30000 });
  await page.evaluate(() => {
    localStorage.clear();
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

  // 确保 personal workspace（默认就是 personal）
  const ws = await page.evaluate(() => localStorage.getItem("zhian-workspace"));
  console.log("当前 workspace:", ws || "(空, default=personal)");

  // 访问 /organization/departments —— personal 视角下应显示 RequireTeamWorkspace 空态
  for (const route of [
    "/organization/departments",
    "/organization/members",
    "/settings/account",
  ]) {
    await page.goto(`${BASE}${route}`, { waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1000));
    const slug = route.replace(/\//g, "_").replace(/^_/, "");
    await page.screenshot({
      path: path.join(OUT, `verify_p0_1_personal${slug}.png`),
      fullPage: true,
    });
    console.log(`✓ personal 视角 ${route} → verify_p0_1_personal${slug}.png`);
  }

  // 切到 team workspace 后再访问 /organization/departments，应显示真实内容
  await page.evaluate(() => {
    const user = JSON.parse(localStorage.getItem("zhian_user") || "null");
    if (user && user.org_id) localStorage.setItem("zhian-workspace", user.org_id);
  });
  await page.goto(`${BASE}/organization/departments`, { waitUntil: "networkidle2", timeout: 20000 });
  await new Promise((r) => setTimeout(r, 1000));
  await page.screenshot({
    path: path.join(OUT, "verify_p0_1_team_org_departments.png"),
    fullPage: true,
  });
  console.log("✓ team 视角 /organization/departments → verify_p0_1_team_org_departments.png");

  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
