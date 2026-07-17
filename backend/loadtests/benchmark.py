"""睿阁压测脚本"""
import os, random, uuid, time, pathlib
from locust import HttpUser, between, task

QUESTIONS = ["员工年假有几天？", "迟到怎么处理？", "加班费怎么算？"]

class ApiUser(HttpUser):
    wait_time = between(3, 8)
    weight = 1

    def on_start(self):
        __p = "PLACEHOLDER"
        email = "lt-" + uuid.uuid4().hex[:8] + "@example.com"
        uname = "lu" + uuid.uuid4().hex[:8]
        r = self.client.post("/api/v1/auth/register", json={
            "email": email, "username": uname,
            "password": __p, "account_type": "personal",
        })
        if r.status_code not in (201, 409):
            print("REGISTER FAIL:", r.status_code)
            return
        r = self.client.post("/api/v1/auth/login", json={
            "identifier": email, "password": __p,
        })
        if r.status_code != 200:
            print("LOGIN FAIL:", r.status_code)
            return
        self.token = r.json()["access_token"]
        self.headers = {"Authorization": "Bearer " + self.token}
        r = self.client.post("/api/v1/knowledge-bases",
            headers=self.headers, params={"workspace": "personal"},
            json={"name": "kb-" + uuid.uuid4().hex[:6]})
        if r.status_code != 201:
            print("KB FAIL:", r.status_code)
            return
        self.kb_id = r.json()["id"]
        md = pathlib.Path("/app/loadtests/golden_handbook.md").read_bytes()
        r = self.client.post("/api/v1/knowledge-bases/" + self.kb_id + "/documents",
            headers=self.headers,
            files={"files": ("handbook.md", md, "text/markdown")})
        if r.status_code == 201:
            docs = r.json().get("documents", [])
            if docs:
                for _ in range(20):
                    time.sleep(1)
                    r2 = self.client.get(
                        "/api/v1/knowledge-bases/" + self.kb_id + "/documents/" + docs[0]["id"],
                        headers=self.headers)
                    if r2.status_code == 200 and r2.json().get("status") == "completed":
                        break

    @task(3)
    def list_kbs(self):
        self.client.get("/api/v1/knowledge-bases",
            headers=self.headers, params={"workspace": "personal"}, name="list_kb")

    @task(2)
    def list_docs(self):
        self.client.get("/api/v1/knowledge-bases/" + self.kb_id + "/documents",
            headers=self.headers, name="list_docs")

    @task(5)
    def ask(self):
        q = random.choice(QUESTIONS)
        with self.client.post("/api/v1/knowledge-bases/" + self.kb_id + "/chat",
            headers=self.headers, json={"message": q},
            stream=True, catch_response=True, name="chat") as resp:
            if resp.status_code == 200:
                for line in resp.iter_lines():
                    if line.startswith(b"event: done"):
                        resp.success()
                        break
            else:
                resp.failure(str(resp.status_code))
