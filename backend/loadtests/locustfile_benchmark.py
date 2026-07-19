"""睿阁 — Benchmark 性能压测（Locust 扩展）

用法：
    locust -f backend/loadtests/locustfile_benchmark.py --host=http://localhost:8000
    locust -f backend/loadtests/locustfile_benchmark.py --host=http://localhost:8000 --headless -u 3 -r 1 --run-time 5m
"""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path

from locust import HttpUser, between, task

# Benchmark 黄金问题（选自 CRAG / golden_qa 风格）
BENCHMARK_QUESTIONS = [
    # 简单事实型
    "员工年假有几天？",
    "迟到怎么处理？",
    "加班费怎么算？",
    "出差补贴是多少？",
    "培训费用谁承担？",
    # 比较型
    "年假和事假有什么区别？",
    "病假和事假扣款方式有何不同？",
    # 条件型
    "试用期员工有年假吗？",
    "工作满一年后年假会增加吗？",
    # 聚合型
    "列举所有请假类型及其规则",
    "列出所有补贴项目和标准",
]

# 多语言支持
EN_QUESTIONS = [
    "How many annual leave days?",
    "What is the overtime pay rate?",
    "What is the travel allowance?",
]

ALL_QUESTIONS = BENCHMARK_QUESTIONS + EN_QUESTIONS

BASE_DIR = Path(__file__).parent
GOLDEN_MD = BASE_DIR / "golden_handbook.md"

PASSWORD = "Test123!@"


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _read_golden_md() -> bytes:
    return GOLDEN_MD.read_bytes()


class BenchmarkSetupUser(HttpUser):
    """Setup 用户：创建 KB + 上传 Golden 文档。只运行一次。"""
    wait_time = between(1, 2)
    weight = 1

    def on_start(self):
        email = f"{_unique('bm-setup')}@example.com"
        username = _unique("bmsetup")
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "password": PASSWORD,
                "account_type": "personal",
            },
            name="register",
        )
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": PASSWORD},
            name="login",
        )
        data = resp.json()
        self.token = data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # 创建 KB
        resp = self.client.post(
            "/api/v1/knowledge-bases",
            headers=self.headers,
            params={"workspace": "personal"},
            json={"name": f"Benchmark库-{uuid.uuid4().hex[:6]}"},
            name="create_kb",
        )
        self.kb_id = resp.json()["id"]

        # 上传 Golden 文档
        md_content = _read_golden_md()
        resp = self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/documents",
            headers=self.headers,
            files={"files": ("golden_handbook.md", md_content, "text/markdown")},
            name="upload_doc",
        )
        self.documents = resp.json().get("documents", [])

    @task
    def health_check(self):
        """简单的健康检查，保持连接。"""
        self.client.get("/health", name="health")


class BenchmarkRetrievalUser(HttpUser):
    """检索性能压测：使用黄金问题测试检索响应时间。"""
    wait_time = between(1, 3)
    weight = 3

    def on_start(self):
        # 复用全局 KB（由 SetupUser 创建，简化方案）
        email = f"{_unique('bm-ret')}@example.com"
        username = _unique("bmret")
        self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": PASSWORD, "account_type": "personal"},
            name="register",
        )
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": PASSWORD},
            name="login",
        )
        self.token = resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # 获取 KB 列表
        resp = self.client.get(
            "/api/v1/knowledge-bases",
            headers=self.headers,
            params={"workspace": "personal"},
            name="list_kb",
        )
        kbs = resp.json().get("items", [])
        self.kb_id = kbs[0]["id"] if kbs else None

    @task(5)
    def search_documents(self):
        """文档搜索（对应 search 限流）。"""
        if not self.kb_id:
            return
        query = random.choice(ALL_QUESTIONS)
        with self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/search",
            headers=self.headers,
            json={"query": query, "top_k": 5},
            catch_response=True,
            name="search",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                resp.success()  # 限流是预期行为
            else:
                resp.failure(f"Search失败: {resp.status_code}")

    @task(2)
    def ask_question(self):
        """对话提问（对应 chat 限流）。"""
        if not self.kb_id:
            return
        query = random.choice(BENCHMARK_QUESTIONS[:5])
        with self.client.post(
            f"/api/v1/knowledge-bases/{self.kb_id}/chat",
            headers=self.headers,
            json={"query": query},
            catch_response=True,
            name="ask_chat",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                resp.success()
            else:
                resp.failure(f"Chat失败: {resp.status_code}")

    @task(1)
    def list_documents(self):
        """文档列表（无限流拖底）。"""
        if not self.kb_id:
            return
        with self.client.get(
            f"/api/v1/knowledge-bases/{self.kb_id}/documents",
            headers=self.headers,
            catch_response=True,
            name="list_docs",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"列表失败: {resp.status_code}")


class BenchmarkRateLimitUser(HttpUser):
    """限流验证压测：连续快速请求验证 429 正确返回。"""
    wait_time = between(0.1, 0.5)  # 快速发送
    weight = 1

    def on_start(self):
        email = f"{_unique('bm-rl')}@example.com"
        username = _unique("bmrl")
        self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "username": username, "password": PASSWORD, "account_type": "personal"},
            name="register",
        )
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"identifier": email, "password": PASSWORD},
            name="login",
        )
        self.token = resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task
    def rapid_ask(self):
        """快速连续提问，触发 chat 限流。"""
        query = random.choice(BENCHMARK_QUESTIONS)
        with self.client.post(
            "/api/v1/ask/chat",
            headers=self.headers,
            json={"query": query},
            catch_response=True,
            name="rapid_ask",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                resp.success()  # 限流正常
            else:
                resp.failure(f"异常状态码: {resp.status_code}")
