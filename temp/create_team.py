"""Create team test accounts"""
import httpx, uuid

BASE = "http://localhost:8000/api/v1"
TOKEN = None

def api(method, path, **kwargs):
    global TOKEN
    headers = kwargs.pop("headers", {})
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = httpx.request(method, f"{BASE}{path}", headers=headers, **kwargs, timeout=30)
    return r

# 1. Register admin user
admin_data = {
    "username": "team_admin",
    "email": "team_admin@test.com",
    "password": "Team@123456",
    "account_type": "enterprise",
    "org_name": "睿阁测试团队",
}
r = api("POST", "/auth/register", json=admin_data)
if r.status_code == 201:
    print(f"Admin registered: {r.json()['id']}")
    TOKEN = r.json()["access_token"]
else:
    print(f"Admin register: {r.status_code} {r.text[:200]}")
    # Try login if already exists
    r = api("POST", "/auth/login", json={"identifier": "team_admin", "password": "Team@123456"})
    if r.status_code == 200:
        TOKEN = r.json()["access_token"]
        print(f"Admin logged in")

if not TOKEN:
    print("Failed to get admin token")
    exit(1)

# 2. Create shared KB
me = api("GET", "/auth/me").json()
org_id = me.get("org_id")
print(f"Org ID: {org_id}")

workspace = str(org_id) if org_id else ""
ws_qs = f"?workspace={workspace}" if workspace else ""

r = api("POST", f"/knowledge-bases{ws_qs}", json={"name": "团队共享资料库", "description": "测试团队的共享知识库"})
if r.status_code == 201:
    kb_id = r.json()["id"]
    print(f"KB created: {kb_id}")
else:
    kb_id = r.json().get("id")
    print(f"KB create: {r.status_code} {r.text[:200]}")

# 3. Upload a test doc
if kb_id:
    content = "睿阁测试团队的共享资料库文档。\n本文档用于测试团队协作功能。\n包括资料库共享、权限管理、审计日志等。".encode("utf-8")
    r = api("POST", f"/knowledge-bases/{kb_id}/documents?workspace={workspace}", files={"files": ("团队介绍.txt", content)})
    print(f"Doc upload: {r.status_code}")

# 4. Create invite code (if org admin)
if org_id:
    r = api("POST", f"/organization/invite-codes{ws_qs}", json={"max_uses": 10})
    if r.status_code == 201:
        code = r.json().get("code", r.json().get("invite_code", ""))
        print(f"Invite code: {code}")
    else:
        print(f"Invite: {r.status_code} {r.text[:200]}")

print("\n=== 团队测试账号 ===")
print(f"管理员: team_admin / Team@123456")
print(f"成员:   (需通过邀请码注册, 见上方或去 /settings/account 页面生成)")
