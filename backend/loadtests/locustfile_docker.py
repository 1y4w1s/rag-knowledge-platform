"""睿阁 — Locust 性能压测（容器内运行版）"""
from __future__ import annotations

import json
import random
import uuid

from locust import HttpUser, between, task

QUESTIONS = ["员工年假有几天？", "迟到怎么处理？", "加班费怎么算？"]
PWD = "Test123!@"


def _u(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class ApiUser(HttpUser):
    """综合用户：注册 → 创建库 → 上传 → 对话"""
    wait_time = between(3, 8)
    weight = 1

    def on_start(self):
        email = f"{_u('perf')}@example.com"
        username = _u("perf")
        resp = self.client.post("/api/v1/auth/register", json={
            "email": email, "username": username,
            "password": PWD, "account_type": "personal",
        })
        if resp.status_code not in (201, 409):
            self.environment.runner.quit()
            return

        resp = self.client.post("/api/v1/auth/login", json={
            "identifier": email, "password": PWD,
        })
        if resp.status_code != 200:
            self.environment.runner.quit()
            return
        self.token = resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # 创建资料库
        resp = self.client.post("/api/v1/knowledge-bases",
            headers=self.headers, params={"workspace": "personal"},
            json={"name": f"库-{uuid.uuid4().hex[:6]}"})
        if resp.status_code != 201:
            self.environment.runner.quit()
            return
        self.kb_id = resp.json()["id"]

        # 上传 golden_handbook.md
        md = (__import__("pathlib").Path(__file__).parent / "golden_handbook.md").read_bytes()
        resp = self.client.post(f"/api/v1/knowledge-bases/{self.kb_id}/documents",
            headers=self.headers,
            files={"files": ("handbook.md", md, "text/markdown")})
        if resp.status_code != 201:
            return
        docs = resp.json().get("documents", [])
        if docs:
            self._poll(docs[0]["id"])

    def _poll(self, doc_id: str, n: int = 20):
        import time
        for _ in range(n):
            time.sleep(1)
            r = self.client.get(
                f"/api/v1/knowledge-bases/{self.kb_id}/documents/{doc_id}",
                headers=self.headers)
            if r.status_code == 200 and r.json().get("status") == "completed":
                return

    @task(3)
    def list_kbs(self):
        self.client.get("/api/v1/knowledge-bases",
            headers=self.headers, params={"workspace": "personal"},
            name="list_kb")

    @task(2)
    def list_docs(self):
        self.client.get(f"/api/v1/knowledge-bases/{self.kb_id}/documents",
            headers=self.headers, name="list_docs")

    @task(5)
    def ask(self):
        q = random.choice(QUESTIONS)
        with self.client.post(f"/api/v1/knowledge-bases/{self.kb_id}/chat",
            headers=self.headers, json={"message": q},
            stream=True, catch_response=True, name="chat") as resp:
            if resp.status_code == 200:
                for line in resp.iter_lines():
                    if line.startswith(b"event: done"):
                        resp.success()
                        break
            else:
                resp.failure(str(resp.status_code))
