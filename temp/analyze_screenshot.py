"""Analyze screenshot via LM Studio vision model"""
import httpx, base64, sys

img_path = r"D:\MyPrograms\rag-knowledge-platform\.reasonix\attachments\clipboard-20260716-204359.053016-000001.png"

with open(img_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode("utf-8")
    data_url = f"data:image/png;base64,{b64}"

payload = {
    "model": "zai-org/glm-4.6v-flash",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": "You are a UI/UX expert. This is a screenshot of a web app sidebar. The avatar button at the bottom-left was clicked and a dropdown menu appeared, but it is being clipped/obscured. Describe EXACTLY what you see: where is the menu positioned relative to the avatar button? Is it fully visible? What is blocking it? Give specific x/y or spatial observations."}
            ]
        }
    ],
    "max_tokens": 1000,
}

try:
    r = httpx.post("http://localhost:1234/v1/chat/completions", json=payload, timeout=120)
    data = r.json()
    content = data["choices"][0]["message"]["content"] or "(empty)"
    print(content)
except Exception as e:
    print(f"Error: {e}")
