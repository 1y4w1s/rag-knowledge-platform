"""Analyze the account settings page layout using Qwen-VL-Plus"""
import os, sys, json, httpx, base64

API_KEY = os.environ.get("TONGYI_API_KEY", "")
if not API_KEY:
    # Try loading from .env
    env_path = r"D:\MyPrograms\rag-knowledge-platform\.env"
    for line in open(env_path, encoding="utf-8"):
        if line.startswith("TONGYI_API_KEY="):
            API_KEY = line.strip().split("=", 1)[1].strip().strip("\"'")
            break

MODEL = "qwen-vl-plus"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# Build a detailed layout description from the accessibility tree
layout_desc = """I am a UI/UX designer reviewing a web page layout. Below is a structured description of the page elements with their exact X,Y coordinates and dimensions. The viewport is 1707x825 pixels. The content area is approximately 640px wide, centered around x=536.

Analyze the layout and identify visual problems. Focus on: spacing inconsistencies, alignment issues, visual hierarchy, information density, contrast, and wasted space. Rank issues by severity (critical/high/medium/low).

=== PAGE LAYOUT ===

HEADER (y=28):
- Logo "睿阁" at x=101,y=28
- Label "企业知识工作台" at x=173,y=39
- Theme button "切换到暗色（当前跟随系统）" at x=1678,y=28

SIDEBAR (x=32, narrow rail style):
- Navigation: 概览, 资料库, 对话 (y=97-197)
- 账号设置 link at y=739 (active state)
- User avatar "HJ" at y=789

MAIN CONTENT AREA:
1. PAGE TITLE (y=151):
   - "账号设置" heading at x=357 (font-serif, large)
   - "ACCOUNT" subtitle at x=442 (smaller, muted)
   → No visual divider between title and content below

2. TWO-COLUMN GRID SECTION:
   LEFT CARD "账号信息" (starts at x=471, y=211):
   - Email field: label "邮箱" at x=379, input at x=517,y=258
   - Account type: label "账号类型" at x=379, input at x=517,y=312
   - Nickname: input at x=439,y=388, "保存" button at x=575,y=388
   - Hint text at y=420
   → Label and input are horizontally aligned (flex row)
   → Button is next to input

   RIGHT CARD "修改密码" (starts at x=801, y=227):
   - "当前密码" label+input at y=262/y=296
   - "新密码" label+input at y=340/y=374
   - "保存密码" button at x=717,y=430
   → Form elements are vertically stacked (narrower card)

3. EMPTY STATE SECTION (starts at y=537):
   - Eyebrow "新账号 · 0 设置项" at x=414,y=537
   - Title "第一次设置，3 分钟搞定" at x=500,y=600
   - Description at y=659-671
   - CTA buttons: "完善个人资料" at x=417,y=729, "修改密码" at x=548,y=729, "加入团队" at x=403,y=776
   - Stats line at y=832-852: "3分钟/全部完成", "2项/必填设置", "随时可改/设置中心", "个人版/免费使用"
   → Notice: this is an EMPTY/ONBOARDING state for new users with no settings configured
   → The buttons' "onClick" handlers scroll to sections below, but those sections are already visible

4. THREE-STEP GUIDE (starts at y=933):
   - Header "从这里开始 3步 3-STEP GUIDE" at y=933
   - 3 columns: "填昵称" (x=418), "修改密码" (x=636), "加入团队（可选）" (x=854)

5. JOIN TEAM FORM (starts at y=1170):
   - "加入团队" heading at y=1170
   - Description text at y=1220
   - Invite code input at y=1300
   - Submit button at y=1381

6. API KEY MANAGER (starts at y=1473):
   - "API Key 管理" heading at y=1473
   - Description text at y=1520
   - Name input at y=1595
   - "创建 Key" button at y=1598 (disabled)
   - "暂无 API Key" empty state at y=1640

7. SESSION CARD (starts at y=1738):
   - "会话" heading at y=1738
   - "退出登录" button at y=1785

TOTAL PAGE HEIGHT: approximately 1860px (requires scrolling on 825px viewport)

=== QUESTIONS ===
1. What are the top 3 visual problems with this layout?
2. How could the spacing between sections be improved?
3. Is the two-column grid for account info + password working well? If not, what's wrong?
4. The empty state (onboarding section) appears AFTER the account info and password forms. Is this the right visual hierarchy?
5. Any issues with text alignment, font sizes, or color contrast?
6. What would you change about the card styling (borders, shadows, padding)?
"""

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "system",
            "content": "You are a professional UI/UX designer reviewing a web page. Provide concise, actionable feedback.",
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": layout_desc},
            ],
        },
    ],
    "max_tokens": 2000,
}

try:
    resp = httpx.post(
        f"{BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    result = resp.json()
    if "choices" in result:
        analysis = result["choices"][0]["message"]["content"]
        print("=== Qwen-VL-Plus ANALYSIS ===")
        print(analysis)
    else:
        print("ERROR:", json.dumps(result, indent=2, ensure_ascii=False))
except Exception as e:
    print(f"API call failed: {e}")
