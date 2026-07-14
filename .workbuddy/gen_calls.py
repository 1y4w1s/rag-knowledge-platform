import json

call1a = """U("2:264", {layout: "vertical", primaryAxisAlignItems: "MIN", counterAxisAlignItems: "MIN", padding: 8, gap: 0, width: "fill_container", height: "hug_contents"})
resultRow1 = I("2:264", {type: "frame", name: "resultRow", layout: "horizontal", primaryAxisAlignItems: "MIN", counterAxisAlignItems: "CENTER", padding: 12, gap: 12, width: "fill_container", height: "hug_contents", fills: []})
resultRow1Main = I(resultRow1, {type: "frame", name: "rowMain", layout: "vertical", primaryAxisAlignItems: "MIN", counterAxisAlignItems: "MIN", gap: 3, width: "fill_container", height: "hug_contents", fills: []})
resultRow1Title = I(resultRow1Main, {type: "text", name: "rowTitle", content: "2024年Q3产品规划.pdf", fontSize: 14, fontName: {family: "Inter", style: "Medium"}, fill: "#18181B", lineHeight: 20, textAutoResize: "HEIGHT", width: "fill_container"})
resultRow1Meta = I(resultRow1Main, {type: "text", name: "rowMeta", content: "产品资料库 · 1.2 MB", fontSize: 12, fontName: {family: "Inter", style: "Regular"}, fill: "#8A8079", lineHeight: 18, textAutoResize: "HEIGHT", width: "fill_container"})
resultRow1Status = I(resultRow1, {type: "text", name: "rowStatus", content: "已可提问", fontSize: 12, fontName: {family: "Inter", style: "Medium"}, fill: "#5BA86E", lineHeight: 16, textAutoResize: "HEIGHT"})
divider1 = I("2:264", {type: "frame", name: "divider", width: "fill_container", height: 1, fill: "#EFEAE4"})"""

call1b = """resultRow2 = I("2:264", {type: "frame", name: "resultRow", layout: "horizontal", primaryAxisAlignItems: "MIN", counterAxisAlignItems: "CENTER", padding: 12, gap: 12, width: "fill_container", height: "hug_contents", fills: []})
resultRow2Main = I(resultRow2, {type: "frame", name: "rowMain", layout: "vertical", primaryAxisAlignItems: "MIN", counterAxisAlignItems: "MIN", gap: 3, width: "fill_container", height: "hug_contents", fills: []})
resultRow2Title = I(resultRow2Main, {type: "text", name: "rowTitle", content: "竞品分析-飞书.docx", fontSize: 14, fontName: {family: "Inter", style: "Medium"}, fill: "#18181B", lineHeight: 20, textAutoResize: "HEIGHT", width: "fill_container"})
resultRow2Meta = I(resultRow2Main, {type: "text", name: "rowMeta", content: "市场研究 · 860 KB", fontSize: 12, fontName: {family: "Inter", style: "Regular"}, fill: "#8A8079", lineHeight: 18, textAutoResize: "HEIGHT", width: "fill_container"})
resultRow2Status = I(resultRow2, {type: "text", name: "rowStatus", content: "整理中", fontSize: 12, fontName: {family: "Inter", style: "Medium"}, fill: "#E8943A", lineHeight: 16, textAutoResize: "HEIGHT"})"""

call2 = """divider2 = I("2:264", {type: "frame", name: "divider", width: "fill_container", height: 1, fill: "#EFEAE4"})
resultRow3 = I("2:264", {type: "frame", name: "resultRow", layout: "horizontal", primaryAxisAlignItems: "MIN", counterAxisAlignItems: "CENTER", padding: 12, gap: 12, width: "fill_container", height: "hug_contents", fills: []})
resultRow3Main = I(resultRow3, {type: "frame", name: "rowMain", layout: "vertical", primaryAxisAlignItems: "MIN", counterAxisAlignItems: "MIN", gap: 3, width: "fill_container", height: "hug_contents", fills: []})
resultRow3Title = I(resultRow3Main, {type: "text", name: "rowTitle", content: "用户访谈记录_08.md", fontSize: 14, fontName: {family: "Inter", style: "Medium"}, fill: "#18181B", lineHeight: 20, textAutoResize: "HEIGHT", width: "fill_container"})
resultRow3Meta = I(resultRow3Main, {type: "text", name: "rowMeta", content: "用户研究 · 24 KB", fontSize: 12, fontName: {family: "Inter", style: "Regular"}, fill: "#8A8079", lineHeight: 18, textAutoResize: "HEIGHT", width: "fill_container"})
resultRow3Status = I(resultRow3, {type: "text", name: "rowStatus", content: "已可提问", fontSize: 12, fontName: {family: "Inter", style: "Medium"}, fill: "#5BA86E", lineHeight: 16, textAutoResize: "HEIGHT"})"""

with open(".workbuddy/call1a.json","w",encoding="utf-8") as f:
    f.write(json.dumps(call1a, ensure_ascii=False))
with open(".workbuddy/call1b.json","w",encoding="utf-8") as f:
    f.write(json.dumps(call1b, ensure_ascii=False))
with open(".workbuddy/call2.json","w",encoding="utf-8") as f:
    f.write(json.dumps(call2, ensure_ascii=False))
print("call1a len:", len(json.dumps(call1a, ensure_ascii=False)))
print("call1b len:", len(json.dumps(call1b, ensure_ascii=False)))
print("call2 len:", len(json.dumps(call2, ensure_ascii=False)))
