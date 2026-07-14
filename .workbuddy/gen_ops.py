import json

def row(name, icon_parent, icon_text, title, meta, badge_fill, badge_text, badge_text_fill):
    return [
        {"kind":"I","name":name,"parent":icon_parent,"props":{"name":"resultRow","type":"FRAME","autoLayout":{"mode":"HORIZONTAL","primaryAxisAlignItems":"MIN","counterAxisAlignItems":"CENTER","padding":{"l":12,"r":12,"t":12,"b":12},"itemSpacing":12,"sizing":{"horizontal":"FILL","vertical":"HUG"}}}},
        {"kind":"I","name":name+"Icon","parent":name,"props":{"name":"rowIcon","type":"FRAME","autoLayout":{"mode":"HORIZONTAL","primaryAxisAlignItems":"CENTER","counterAxisAlignItems":"CENTER","padding":{"l":0,"r":0,"t":0,"b":0},"sizing":{"horizontal":"FIXED","vertical":"FIXED"}},"size":{"width":36,"height":36},"cornerRadius":8,"fills":[{"r":0.961,"g":0.949,"b":0.929,"a":1}]}},
        {"kind":"I","name":name+"IconLabel","parent":name+"Icon","props":{"name":"rowIconLabel","type":"TEXT","characters":icon_text,"style":{"fontSize":11,"fontName":{"family":"Inter","style":"SemiBold"},"fills":[{"r":0.796,"g":0.42,"b":0.239,"a":1}],"textAlignHorizontal":"CENTER"}}},
        {"kind":"I","name":name+"Main","parent":name,"props":{"name":"rowMain","type":"FRAME","autoLayout":{"mode":"VERTICAL","primaryAxisAlignItems":"MIN","counterAxisAlignItems":"MIN","padding":{"l":0,"r":0,"t":0,"b":0},"itemSpacing":3,"sizing":{"horizontal":"FILL","vertical":"HUG"}}}},
        {"kind":"I","name":name+"Title","parent":name+"Main","props":{"name":"rowTitle","type":"TEXT","characters":title,"style":{"fontSize":14,"fontName":{"family":"Inter","style":"Medium"},"fills":[{"r":0.094,"g":0.094,"b":0.106,"a":1}],"lineHeight":{"value":20,"unit":"PIXELS"}}}},
        {"kind":"I","name":name+"Meta","parent":name+"Main","props":{"name":"rowMeta","type":"TEXT","characters":meta,"style":{"fontSize":12,"fontName":{"family":"Inter","style":"Regular"},"fills":[{"r":0.541,"g":0.502,"b":0.475,"a":1}],"lineHeight":{"value":18,"unit":"PIXELS"}}}},
        {"kind":"I","name":name+"Badge","parent":name,"props":{"name":"rowBadge","type":"FRAME","autoLayout":{"mode":"HORIZONTAL","primaryAxisAlignItems":"CENTER","counterAxisAlignItems":"CENTER","padding":{"l":10,"r":10,"t":5,"b":5},"itemSpacing":0,"sizing":{"horizontal":"HUG","vertical":"HUG"}},"cornerRadius":999,"fills":[badge_fill]}},
        {"kind":"I","name":name+"BadgeText","parent":name+"Badge","props":{"name":"rowBadgeText","type":"TEXT","characters":badge_text,"style":{"fontSize":12,"fontName":{"family":"Inter","style":"Medium"},"fills":[badge_text_fill],"lineHeight":{"value":16,"unit":"PIXELS"}}}},
    ]

GREEN = {"r":0.357,"g":0.659,"b":0.431,"a":0.14}
GREEN_T = {"r":0.357,"g":0.659,"b":0.431,"a":1}
AMBER = {"r":0.91,"g":0.58,"b":0.227,"a":0.16}
AMBER_T = {"r":0.91,"g":0.58,"b":0.227,"a":1}

batch_a = [
    {"kind":"U","node":"2:264","props":{"autoLayout":{"mode":"VERTICAL","primaryAxisAlignItems":"MIN","counterAxisAlignItems":"MIN","padding":{"l":8,"r":8,"t":8,"b":8},"itemSpacing":0,"sizing":{"horizontal":"FILL","vertical":"HUG"}}}},
]
batch_a += row("resultRow1","2:264","PDF","2024年Q3产品规划.pdf","产品资料库 · 1.2 MB",GREEN,"已可提问",GREEN_T)
batch_a += [{"kind":"I","name":"divider1","parent":"2:264","props":{"name":"divider","type":"FRAME","sizing":{"horizontal":"FILL","vertical":"FIXED"},"height":1,"fills":[{"r":0.937,"g":0.918,"b":0.894,"a":1}]}}]
batch_a += row("resultRow2","2:264","DOC","竞品分析-飞书.docx","市场研究 · 860 KB",AMBER,"整理中",AMBER_T)

batch_b = []
batch_b += [{"kind":"I","name":"divider2","parent":"2:264","props":{"name":"divider","type":"FRAME","sizing":{"horizontal":"FILL","vertical":"FIXED"},"height":1,"fills":[{"r":0.937,"g":0.918,"b":0.894,"a":1}]}}]
batch_b += row("resultRow3","2:264","MD","用户访谈记录_08.md","用户研究 · 24 KB",GREEN,"已可提问",GREEN_T)

with open(".workbuddy/ops_a.json","w",encoding="utf-8") as f:
    f.write(json.dumps(batch_a, ensure_ascii=False, indent=2))
with open(".workbuddy/ops_b.json","w",encoding="utf-8") as f:
    f.write(json.dumps(batch_b, ensure_ascii=False, indent=2))
print("batch_a ops:", len(batch_a))
print("batch_b ops:", len(batch_b))
