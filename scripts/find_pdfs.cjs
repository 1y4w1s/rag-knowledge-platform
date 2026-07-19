const puppeteer = require("puppeteer-core");

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = "http://localhost:5173";

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const page = await browser.newPage();
    await page.goto(`${BASE}/login`, { waitUntil: "networkidle2", timeout: 20000 });
    await page.waitForSelector("#identifier", { timeout: 15000 });
    await page.type("#identifier", "demo_admin", { delay: 5 });
    await page.type('input[type="password"]', "password123", { delay: 5 });
    await Promise.all([
      page.waitForNavigation({ waitUntil: "networkidle2", timeout: 20000 }),
      page.click('button[type="submit"]'),
    ]);

    // 切 personal
    await page.evaluate(() => {
      localStorage.setItem("zhian-workspace", JSON.stringify({ id: "personal" }));
    });
    await page.reload({ waitUntil: "networkidle2", timeout: 20000 });
    await new Promise((r) => setTimeout(r, 1500));

    const result = await page.evaluate(async () => {
      const out = [];
      const list = await fetch("/api/v1/knowledge-bases?limit=50", { credentials: "include" });
      const data = await list.json();
      const kbs = data.items || [];
      for (const kb of kbs) {
        const docs = await fetch(`/api/v1/knowledge-bases/${kb.id}/documents?limit=20`, { credentials: "include" });
        const ddata = await docs.json();
        for (const d of ddata.items || []) {
          if ((d.filename || "").toLowerCase().endsWith(".pdf")) {
            out.push({ kb: kb.name, kbId: kb.id, filename: d.filename, status: d.status, docId: d.id });
          }
        }
      }
      return out;
    });

    console.log("All PDFs in personal workspace:");
    result.forEach(r => console.log(`  ${r.kb} | ${r.filename} | ${r.status} | ${r.docId}`));
  } finally {
    await browser.close();
  }
})();
