"""睿阁 — Locust 性能压测脚本

用法：locust -f backend/loadtests/locustfile.py --host=http://localhost:8000
访问 http://localhost:8089 启动压测。
或直接运行：locust -f backend/loadtests/locustfile.py --host=http://localhost:8000 --headless -u 5 -r 1 --run-time 2m
"""
from __future__ import annotations

import json
import random
import uuid
from pathlib import Path

from locust import HttpUser, between, task

# Golden 测试问题（选自 golden_qa.json）
GOLDEN_QUESTIONS = [
    "员工年假有几天？",
    "迟到怎么处理？",
    "加班费怎么算？",
    "出差补贴是多少？",
    "培训费用谁承担？",
]

BASE_DIR = Path(__file__).parent
GOLDEN_MD = BASE_DIR / "golden_handbook.md"

PASSWORD = "Test123!@"

# ── 辅助函数 ─────────────────────────────────────────────


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _read_golden_md() -> bytes:
    return GOLDEN_MD.read_bytes()


# ── 用户场景 1: 注册 + 登录 ────────────────────────────


class AuthUser(HttpUser):
    """场景 1：注册新用户 + 登录获取 token。轻量级，用于验证认证链路。"""
    wait_time = between(1, 3)
    weight = 1

    def on_start(self):
        self.email = f"{_unique('load-auth')}@example.com"
        self.username = _unique("loadauth")
        self.token = None

    @task
    def register_and_login(self):
        # 注册
        with self.client.post(
            "/api/v1/auth/register",
            json={
                "email": self.email,
                "username": self.username,
                "password": PASSWORD,
                "account_type": "personal",
            },
            catch_response=True,
            name="register",
        ) as resp:
            if resp.status_code == 201:
                resp.success()
            elif resp.status_code == 409:
                resp.success()  # 用户已存在（重跑时）
            else:
                resp.failure(f"注册失败: {resp.status_code}")

        # 登录
        with self.client.post(
            "/api/v1/auth/login",
            json={"identifier": self.email, "password": PASSWORD},
            catch_response=True,
            name="login",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.token = data["access_token"]
                resp.success()
            else:
                resp.failure(f"登录失败: {resp.status_code}")


# ── 用户场景 2: 资料库 CRUD ────────────────────────────


class KbUser(HttpUser):
    """场景 2：创建资料库 + 列表查询。中等负载。"""
    wait_time = between(2, 5)
    weight = 2

    def on_start(self):
        email = f"{_unique('load-kb')}@example.com"
        username = _unique("loadkb")
        with self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "password": PASSWORD,
                "account_type": "personal",
            },
            name="register",
        ):
            pass
        with self.client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": PASSWORD},
            name="login",
        ) as resp:
            data = resp.json()
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
            self.kb_id = None

    @task(3)
    def list_knowledge_bases(self):
        with self.client.get(
            "/api/v1/knowledge-bases",
            headers=self.headers,
            params={"workspace": "personal"},
            catch_response=True,
            name="list_kb",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"列表失败: {resp.status_code}")

    @task(1)
    def create_knowledge_base(self):
        name = f"压测库-{uuid.uuid4().hex[:6]}"
        with self.client.post(
            "/api/v1/knowledge-bases",
            headers=self.headers,
            params={"workspace": "personal"},
            json={"name": name},
            catch_response=True,
            name="create_kb",
        ) as resp:
            if resp.status_code == 201:
                self.kb_id = resp.json()["id"]
                resp.success()
            else:
                resp.failure(f"创建失败: {resp.status_code}")


# ── 用户场景 3: 文档上传 ──────────────────────────────


class UploadUser(HttpUser):
    """场景 3：上传文档 + 等待 ingestion 完成。重量级。"""
    wait_time = between(3, 8)
    weight = 2

    def on_start(self):
        email = f"{_unique('load-up')}@example.com"
        username = _unique("loadup")
        with self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "password": PASSWORD,
                "account_type": "personal",
            },
            name="register",
        ):
            pass
        with self.client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": PASSWORD},
            name="login",
        ) as resp:
            data = resp.json()
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        # 创建资料库
        with self.client.post(
            "/api/v1/knowledge-bases",
            headers=self.headers,
            params={"workspace": "personal"},
            json={"name": f"上传库-{uuid.uuid4().hex[:6]}"},
            name="create_kb_prep",
        ) as resp:
            self.kb_id = resp.json()["id"]

    @task
    def upload_document(self):
        md_content = _read_golden_md()
        with self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/documents",
            headers=self.headers,
            files={"files": ("handbook.md", md_content, "text/markdown")},
            catch_response=True,
            name="upload_doc",
        ) as resp:
            if resp.status_code == 201:
                resp.success()
                docs = resp.json().get("documents", [])
                if docs:
                    self._poll_ingestion(docs[0]["id"])
            else:
                resp.failure(f"上传失败: {resp.status_code}")

    def _poll_ingestion(self, doc_id: str, max_retries: int = 10):
        """轮询文档状态直到 completed 或超时。"""
        import time
        for _ in range(max_retries):
            time.sleep(1)
            with self.client.get(
                f"/api/v1/knowledge-bases/{self.kb_id}/documents/{doc_id}",
                headers=self.headers,
                catch_response=True,
                name="poll_doc",
            ) as resp:
                if resp.status_code == 200:
                    status = resp.json().get("status")
                    if status == "completed":
                        return
                    elif status == "failed":
                        return


# ── 用户场景 4: 对话提问 ──────────────────────────────


class ChatUser(HttpUser):
    """场景 4：上传文档后对话提问。最重量级，模拟真实 RAG 使用。"""
    wait_time = between(5, 15)
    weight = 1

    def on_start(self):
        email = f"{_unique('load-chat')}@example.com"
        username = _unique("loadchat")
        with self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "password": PASSWORD,
                "account_type": "personal",
            },
            name="register",
        ):
            pass
        with self.client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": PASSWORD},
            name="login",
        ) as resp:
            data = resp.json()
            self.token = data["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        # 创建资料库并上传文档
        with self.client.post(
            "/api/v1/knowledge-bases",
            headers=self.headers,
            params={"workspace": "personal"},
            json={"name": f"对话库-{uuid.uuid4().hex[:6]}"},
            name="create_kb_prep",
        ) as resp:
            self.kb_id = resp.json()["id"]
        self._upload_and_wait()

    def _upload_and_wait(self):
        md_content = _read_golden_md()
        with self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/documents",
            headers=self.headers,
            files={"files": ("handbook.md", md_content, "text/markdown")},
            name="upload_doc_prep",
        ) as resp:
            if resp.status_code == 201:
                docs = resp.json().get("documents", [])
                if docs:
                    self.doc_id = docs[0]["id"]
                    self._poll_ingestion(self.doc_id)

    def _poll_ingestion(self, doc_id: str, max_retries: int = 15):
        import time
        for _ in range(max_retries):
            time.sleep(1)
            with self.client.get(
                f"/api/v1/knowledge-bases/{self.kb_id}/documents/{doc_id}",
                headers=self.headers,
                name="poll_doc_prep",
            ) as resp:
                if resp.status_code == 200 and resp.json().get("status") == "completed":
                    return

    @task
    def ask_question(self):
        question = random.choice(GOLDEN_QUESTIONS)
        with self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/chat",
            headers=self.headers,
            json={"message": question},
            stream=True,
            catch_response=True,
            name="chat_ask",
        ) as resp:
            if resp.status_code == 200:
                # 读取 SSE 流直到 done 事件
                for line in resp.iter_lines():
                    if line.startswith("event: done"):
                        resp.success()
                        break
                    elif line.startswith("event: error"):
                        resp.failure("对话返回 error 事件")
                        break
            else:
                resp.failure(f"对话失败: {resp.status_code}")
