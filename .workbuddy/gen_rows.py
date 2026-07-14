import json

def row(name, title, meta, status, status_fill):
    return [
        {"kind":"I","name":name,"parent":"2:264","props":{"name":"resultRow","type":"FRAME","autoLayout":{"mode":"HORIZONTAL","primaryAxisAlignItems":"MIN","counterAxisAlignItems":"CENTER","padding":{"l":12,"r":14,"t":12,"b":12},"itemSpacing":12,"sizing":{"horizontal":"FILL","vertical":"HUG"}}}},
        {"kind":"I","name":name+"Main","parent":name,"props":{"name":"rowMain","type":"FRAME","autoLayout":{"mode":"VERTICAL","primaryAxisAlignItems":"MIN","counterAxisAlignItems":"MIN","padding":{"l":0,"r":0,"t":0,"b":0},"itemSpacing":3,"sizing":{"horizontal":"FILL","vertical":"HUG"}}}},
        {"kind":"I","name":name+"Title","parent":name+"Main","props":{"name":"rowTitle","type":"TEXT","characters":title,"style":{"fontSize":14,"fontName":{"family":"Inter","style":"Medium"},"fills":[{"r":0.094,"g":0.094,"b":0.106,"a":1}],"lineHeight":{"value":20,"unit":"PIXELS"}}}},
        {"kind":"I","name":name+"Meta","parent":name+"Main","props":{"name":"rowMeta","type":"TEXT","characters":meta,"style":{"fontSize":12,"fontName":{"family":"Inter","style":"Regular"},"fills":[{"r":0.541,"g":0.502,"b":0.475,"a":1}],"lineHeight":{"value":18,"unit":"PIXELS"}}}},
        {"kind":"I","name":name+"Status","parent":name,"props":{"name":"rowStatus","type":"TEXT","characters":status,"style":{"fontSize":12,"fontName":{"family":"Inter","style":"Medium"},"fills":[status_fill],"lineHeight":{"value":16,"unit":"PIXELS"}}}}
    ]

GREEN_T = {"r":0.357,"g":0.659,"b":0.431,"a":1}
AMBER_T = {"r":0.91,"g":0.58,"b":0.227,"a":1}

row1 = row("resultRow1","2024年Q3产品规划.pdf","产品资料库 · 1.2 MB","已可提问",GREEN_T)
row2 = row("resultRow2","竞品分析-飞书.docx","市场研究 · 860 KB","整理中",AMBER_T)
row3 = row("resultRow3","用户访谈记录_08.md","用户研究 · 24 KB","已可提问",GREEN_T)

setup = [{"kind":"U","node":"2:264","props":{"autoLayout":{"mode":"VERTICAL","primaryAxisAlignItems":"MIN","counterAxisAlignItems":"MIN","padding":{"l":8,"r":8,"t":8,"b":8},"itemSpacing":0,"sizing":{"horizontal":"FILL","vertical":"HUG"}}}}]
divider = [{"kind":"I","name":"dividerX","parent":"2:264","props":{"name":"divider","type":"FRAME","sizing":{"horizontal":"FILL","vertical":"FIXED"},"height":1,"fills":[{"r":0.937,"g":0.918,"b":0.894,"a":1}]}}]

for fn, data in [("setup.json",setup),("row1.json",row1),("row2.json",row2),("row3.json",row3),("divider.json",divider)]:
    s = json.dumps(data, ensure_ascii=False)
    with open(".workbuddy/"+fn,"w",encoding="utf-8") as f:
        f.write(s)
    print(fn, "len=", len(s))
