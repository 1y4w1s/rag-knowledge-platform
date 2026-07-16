"""Print test account info"""
import requests

BASE = "http://localhost:8000/api/v1"

login = requests.post(f"{BASE}/auth/login", json={
    "identifier": "testuser_ui",
    "password": "Test@123456"
})
print(f"Login: {login.status_code}")
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Get user info
me = requests.get(f"{BASE}/auth/me", headers=headers).json()
print(f"User: testuser_ui / Test@123456")
print(f"Email: testui@test.com")
print(f"Account type: {me.get('account_type')}")

# List KBs
kbs = requests.get(f"{BASE}/knowledge-bases?workspace=personal", headers=headers).json()
items = kbs.get("items", [])
print(f"\nKnowledge bases ({len(items)}):")
for kb in items:
    r = requests.get(f"{BASE}/knowledge-bases/{kb['id']}?workspace=personal", headers=headers)
    d = r.json()
    print(f"  [{d.get('document_count', 0)} docs] {kb['name']}")
