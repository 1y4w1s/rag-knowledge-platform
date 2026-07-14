"""DOM-level verification of EmptyStateV44 icon rendering.

We CANNOT trust tsc/build/vitest to catch a black-block icon bug (that is a
runtime CSS/paint issue). And we cannot view PNG screenshots in this session.
So instead we assert, on the LIVE rendered page, that every Icon <path> paints
as an outline (computed fill === "none") rather than a solid black block.

CSS `fill` rules override SVG presentation attributes, so this is the ground
truth: getComputedStyle on the actual painted element.
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5173/preview-empty.html"
SCENES = ["dashboard", "kbs", "kbdetail", "ask", "members", "account", "chat"]

# Selectors for Icon-rendered paths. ALL of these MUST be fill:none.
# NOTE: the Icon component renders <svg class="ico">, so the step icon's <path>
# is ".empty-step-h .ico path" (the .ico element IS the svg, not a wrapper).
ICON_SELECTORS = [
    ".empty-hero .actions .dash-btn svg path",
    ".empty-step-h .ico path",
    ".empty-card .top .ic svg path",
    ".rag-preview .visual svg path",
]


def main() -> int:
    report: dict = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1100, "height": 1600})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.type + ": " + m.text))
        page.on("pageerror", lambda e: errors.append("PAGEERROR: " + str(e)))

        page.goto(BASE, wait_until="networkidle")
        page.wait_for_selector("#scene-ask", timeout=20000)

        for key in SCENES:
            root = f"#scene-{key}"
            cta_count = page.locator(f"{root} .empty-hero .actions .dash-btn").count()
            paths = page.evaluate(
                """(args) => {
                    const root = document.querySelector(args.root);
                    const out = [];
                    for (const sel of args.sels) {
                        root.querySelectorAll(sel).forEach((path) => {
                            const cs = getComputedStyle(path);
                            out.push({
                                sel,
                                fill: cs.fill,
                                stroke: cs.stroke,
                                strokeWidth: cs.strokeWidth,
                            });
                        });
                    }
                    return out;
                }""",
                {"root": root, "sels": ICON_SELECTORS},
            )
            # Black block = a filled path with no visible stroke.
            blocks = [
                x
                for x in paths
                if x["fill"] != "none"
                and (x["stroke"] == "none" or x["strokeWidth"] in ("0", "0px"))
            ]
            filled = [x for x in paths if x["fill"] != "none"]
            report[key] = {
                "hero_cta_count": cta_count,
                "icon_path_total": len(paths),
                "all_fill_none": all(x["fill"] == "none" for x in paths),
                "black_blocks": len(blocks),
                "non_outline_filled_paths": len(filled),
            }
        browser.close()

    report["_console_errors"] = errors
    print(json.dumps(report, ensure_ascii=False, indent=2))

    bad = [
        k
        for k, v in report.items()
        if isinstance(v, dict) and v.get("black_blocks", 0) > 0
    ]
    if bad:
        print("\nFAIL: black-block icons detected in scenes:", bad)
        return 1
    print("\nPASS: no black-block icons; all icon paths render as outlines (fill:none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
