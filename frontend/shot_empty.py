from playwright.sync_api import sync_playwright
import pathlib

OUT = pathlib.Path(r"D:\MyPrograms\rag-knowledge-platform\frontend\shot_empty")
OUT.mkdir(exist_ok=True)

URL = "http://localhost:5173/preview-empty.html"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(
        viewport={"width": 1100, "height": 1400}, device_scale_factor=2
    )
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(2000)  # 等字体/动画稳定
    page.screenshot(path=str(OUT / "all.png"), full_page=True)
    for key in ["dashboard", "kbs", "kbdetail", "ask", "members", "account", "chat"]:
        el = page.query_selector(f"#scene-{key}")
        if el:
            el.screenshot(path=str(OUT / f"{key}.png"))
            print("shot", key)
        else:
            print("MISSING", key)
    browser.close()
print("DONE")
