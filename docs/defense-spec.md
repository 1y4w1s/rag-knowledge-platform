# RAG 弹性防线 — SPEC

> 版本：v1.0 · 2026-07-15
> 覆盖：睿阁 RAG 系统的防御体系说明，非功能特性的设计文档，供面试/架构评审/运维参考。

---

## 目录

1. [架构总览](#1-架构总览)
2. [重试层](#2-重试层)
3. [熔断器](#3-熔断器)
4. [降级阶梯](#4-降级阶梯)
5. [超时预算](#5-超时预算)
6. [数据质量校验](#6-数据质量校验)
7. [限流与资源防护](#7-限流与资源防护)
8. [幂等性](#8-幂等性)
9. [安全过滤](#9-安全过滤)
10. [可观测性](#10-可观测性)
11. [未覆盖的风险](#11-未覆盖的风险)
12. [测试指引](#12-测试指引)

---

## 1. 架构总览

```
用户请求
  │
  ├─ [入口] 限流关卡 ─────────── api_rate_limit.py
  │     └─ 降级感知配额收紧 ─── degradation_multiplier()
  │
  ├─ [安全] 输入过滤 ──────────── safety_filter.py
  │
  ├─ [判断] 降级评估 ──────────── degradation.py
  │     ├─ L4 ALL_DOWN → 短路返回
  │     └─ L1/L2/L3 → 跳过对应服务
  │
  ├─ [检索] 检索层 ───────────── retrieval.py
  │     ├─ 向量召回 + FTS 并行
  │     ├─ 嵌入调用包装 async_retry + 熔断器
  │     └─ 连接池复用 http_client.py
  │
  ├─ [重排] Rerank ───────────── rerank.py
  │     ├─ 空结果/失败 → 回落 RRF 顺序
  │     └─ API 调用包装 async_retry + 熔断器
  │
  ├─ [生成] LLM 调用 ─────────── generation.py
  │     ├─ 流式重连 retry_stream + 熔断器
  │     └─ asyncio.wait_for 超时
  │
  ├─ [输出] 引用溯源 ─────────── retrieval.py chunk_to_citation
  │
  └─ [审计] 事件记录 ─────────── audit_logs.py
```

---

## 2. 重试层

**文件**：`app/core/retry.py`

### `async_retry()`

```
def async_retry(
    func, *args,
    max_retries=2,    ← config: retry_max_attempts
    base_delay=1.0,   ← config: retry_base_delay
    max_delay=30.0,   ← config: retry_max_delay
    breaker_name=None,
)
```

**行为**：
- 首次执行 + 最多 `max_retries` 次重试
- 退避公式：`delay = min(base_delay × 2^attempt, max_delay)`
- jitter：`uniform(-delay × 0.1, delay × 0.1)`
- 重试判定：`should_retry()` 区分可重试/不可重试异常

**`should_retry()` 判定规则**：

| 异常特征 | 可重试？ | 原因 |
|----------|---------|------|
| 429 Too Many Requests | ✅ | 限流后可能恢复 |
| 400/401/403/404/422 | ❌ | 客户端错误，重试无意义 |
| 502/503/504 | ✅ | 服务端临时故障 |
| timeout / connection reset / EOF | ✅ | 网络瞬态故障 |

### `retry_stream()`

适用于 SSE 流式场景。连接中断时重新建立 HTTP 连接并继续流式读取。

```
def retry_stream(
    stream_factory,     ← 每次重连时重新调用
    max_retries=2,
    breaker_name=None,
)
```

**关键行为**：一旦成功 yield 过至少一个 token，后续中断不打开熔断器（部分输出的损失已无法挽回）。

### 调用点

| 调用方 | 重试函数 | breaker_name | 文件:行 |
|--------|---------|--------------|---------|
| embedding API | `async_retry(_embed_tongyi, ...)` | `tongyi_embed` | embedder.py:216 |
| rerank API | `async_retry(_rerank_tongyi, ...)` | `tongyi_rerank` | rerank.py:123 |
| LLM streaming | `retry_stream(_make_stream, ...)` | `deepseek_llm` | generation.py:369 |
| Agent 工具调度 | `async_retry(_dispatch_tool, ...)` | 无（工具失败≠后端不可用） | runtime.py:226 |

---

## 3. 熔断器

**文件**：`app/core/retry.py` class `CircuitBreaker`

### 状态机

```
CLOSED ──(连续 failure_threshold 次失败)──→ OPEN
OPEN ──(recovery_timeout 秒后)──→ HALF_OPEN
HALF_OPEN ──(成功)──→ CLOSED
HALF_OPEN ──(再失败)──→ OPEN
```

### 配置

| 参数 | 默认值 | 环境变量 |
|------|--------|---------|
| `failure_threshold` | 5 | `CIRCUIT_BREAKER_FAILURE_THRESHOLD` |
| `recovery_timeout` | 30s | `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` |

### 触发链

```
API 调用失败 → async_retry 重试耗尽
  → record_failure() 打开熔断器
  → 下次 assess_degradation() 读到 breaker state=open
  → 判定该服务不可用，触发对应降级等级
  → 后续请求走降级路径直到熔断器恢复
```

### 全局注册表

```python
get_breaker("deepseek_llm")    # LLM 调用
get_breaker("tongyi_rerank")   # Rerank 调用
get_breaker("tongyi_embed")    # Embedding 调用
```

### 结构化日志事件

每次状态变更输出 JSON 格式日志行，包含：

```json
{"event_type":"circuit_breaker_state_change","breaker":"deepseek_llm",
 "from_state":"closed","to_state":"open","failures":5}
```

---

## 4. 降级阶梯

**文件**：`app/core/degradation.py`

### DegradationLevel

| 等级 | 含义 | 行为 |
|------|------|------|
| **L0 NORMAL** | 全部正常 | 标准 RAG 流程 |
| **L1 LLM_DOWN** | LLM 不可用 | 返回 FTS 片段原文 + 降级说明文本 |
| **L2 RERANK_DOWN** | Rerank 不可用 | 使用 RRF 原始排序（已在 rerank.py 中 fallback） |
| **L3 EMBED_DOWN** | 嵌入服务不可用 | 仅使用全文检索（FTS-only） |
| **L4 ALL_DOWN** | 多服务同时熔断 | 立即短路返回「服务暂不可用」 |

### 评估函数

```python
def assess_degradation() -> DegradationLevel
```

**判定逻辑**：
1. `degradation_enabled=False` → 始终 L0
2. 同时 ≥ 2 个熔断器打开 → L4
3. 单服务熔断 → 对应等级（LLM > Rerank > Embedding 优先级）
4. 熔断器全部关闭 → L0

### 抖动抑制

```python
def apply_stabilization(theoretical: DegradationLevel) -> DegradationLevel
```

**规则**：

| 方向 | 行为 |
|------|------|
| 恶化（L0→L1, L1→L2） | 立即生效 |
| 改善（L1→L0） | 需等待 `degradation_cooldown_seconds`（默认 60s） |
| L4→\* 恢复 | 旁路冷却，立即生效 |
| 等级不变 | 无操作 |

### 降级到 LLM 路径的短路

在 `chat.py:stream_chat_events()` 中：

```
if deg_level >= 4:  # ALL_DOWN
    发送 degradation_message(ALL_DOWN)
    落库
    返回 done
    不执行任何检索或 LLM 调用
```

### 降级对限流的反馈

在 `api_rate_limit.py` 中：

| 降级等级 | 限流配额比例 |
|----------|------------|
| L0 | 100% (30 chats/hr) |
| L1 | 50% (15 chats/hr) |
| L2 | 50% (15 chats/hr) |
| L3 | 30% (9 chats/hr) |
| L4 | 30% (9 chats/hr) |

---

## 5. 超时预算

### 配置

| 参数 | 默认值 | 作用域 |
|------|--------|--------|
| `llm_timeout_seconds` | 120.0 | DeepSeek 流式调用 |
| `rerank_timeout_seconds` | 60.0 | 通义 rerank |
| `embed_timeout_seconds` | 60.0 | 通义嵌入 |
| `retrieval_timeout_seconds` | 30.0 | 已定义，待接线到检索层 |

### 实现

使用 `asyncio.wait_for()` 而非 `httpx.AsyncClient(timeout=...)` 作为主要超时手段：

```
# embedder.py
resp = await asyncio.wait_for(
    client.post(TONGYI_EMBED_URL, headers=..., json=...),
    timeout=settings.embed_timeout_seconds,
)
```

`httpx.AsyncClient(timeout=settings.xxx + 5.0)` 作为安全网（比 asyncio 超时多 5s）。

### 连接池

共享客户端（`app/core/http_client.py`）：

| 客户端 | 服务 | 连接池大小 |
|--------|------|-----------|
| `get_deepseek_client()` | DeepSeek LLM | `http_max_connections`（默认 10） |
| `get_tongyi_client()` | 通义嵌入 + rerank | `http_max_connections`（默认 10） |

---

## 6. 数据质量校验

### Embedding 输出校验

**文件**：`embedder.py` `_validate_vectors()`

| 校验项 | 检测方式 | 失败后果 |
|--------|---------|---------|
| 维度 | `len(v) != EMBEDDING_DIM` | ValueError |
| 非数值 | `not isinstance(x, (int, float))` | ValueError |
| NaN/Inf | `math.isnan(x) or math.isinf(x)` | ValueError |
| 零向量 | `norm < 1e-10` | ValueError |

所有失败最终被 `try_embed_texts()` 捕获 → 降级为 FTS-only。

### 响应一致性校验

**文件**：`embedder.py` `_check_response_consistency()`

```
同一输入 → SHA256(input) → 存储响应 hash
下次同一输入 → 计算响应 hash → 比较
不一致 → logger.warning("嵌入响应不一致（可能版本漂移）")
```

检测场景：负载均衡打到不同版本的 embedding 模型。

### Embedding 缓存

`_EmbeddingCache` — LRU + TTL（最大 5000 条，TTL 1 小时）。
缓存 key 为 `SHA256(text)[:24]`。

---

## 7. 限流与资源防护

**文件**：`app/services/auth/api_rate_limit.py`

### 配额

| 操作 | 配额（L0） | 窗口 |
|------|-----------|------|
| 对话 (`chat`) | 30/hr | 滑动 1h |
| 上传 (`upload`) | 20/hr | 滑动 1h |

### 并发安全

`threading.Lock` 保护 `_prune()` → `append()` 临界区，防止竞态条件。

### 实现机制

滑动窗口 + 过期修剪：

```python
timestamps = [t for t in _counters.get(key, []) if t > now - window]
if len(timestamps) >= effective_max:
    raise RateLimitError(...)
timestamps.append(now)
```

---

## 8. 幂等性

**文件**：`generate_faq_draft.py`

写操作（创建 FAQ 草稿）在重试时自动去重：

```
检查同 run_id + filename + status=pending 的 AgentApproval
  → 已存在：返回现有 approval_id（幂等）
  → 不存在：创建新的
```

---

## 9. 安全过滤

**文件**：`app/services/rag/safety_filter.py`

| 过滤层 | 方式 | 触发时机 |
|--------|------|---------|
| 输入安全 | 正则匹配危险指令 | 检索前，立即阻断 |
| 引用溯源 | citations（文档名+页码+原文） | 输出时 |
| 权限隔离 | `visible_kb_ids` + `workspace_scope` | 检索时 |
| 审计日志 | `audit_logs` 记录关键操作 | 操作后 |

**不足**：无输出安全过滤（LLM 生成内容未做二次校验）。

---

## 10. 可观测性

### 结构化日志

| 事件类型 | 输出位置 | 内容 |
|----------|---------|------|
| 熔断器状态变更 | `retry.py` | `event_type=circuit_breaker_state_change` + 状态 |
| 降级等级变更 | `degradation.py` | 旧等级 → 新等级 + 标签 |
| 降级抖动抑制 | `degradation.py` | 理论等级 vs 实际等级 + 冷却剩余时间 |

### Health 端点

`GET /health` 响应结构：

```json
{
  "status": "ok|degraded",
  "database": "ok|error",
  "degradation": {
    "level": 0,
    "label": "正常",
    "breakers": {
      "deepseek_llm": {"state": "closed", "failures": 0},
      "tongyi_rerank": {"state": "closed", "failures": 0},
      "tongyi_embed": {"state": "closed", "failures": 0}
    },
    "recent_events": [
      {"timestamp": ..., "old_level": 0, "new_level": 1, "label": "..."}
    ]
  }
}
```

---

## 11. 未覆盖的风险

### 已识别但未实现

| 风险 | 原因 | 优先级 |
|------|------|--------|
| `retrieval_timeout_seconds` 未接线 | 需要为 `retrieve_chunks()` 加 `asyncio.wait_for` | 中 |
| 输出安全过滤 | LLM 输出可能含敏感内容，需正则/模式匹配过滤 | 中 |
| 降级阶梯的 `degradation_requires_*()` 未使用 | 设计用于跳过特定服务，待下层调用方接入 | 低 |
| 检索层无独立超时 | DB 查询无超时保护，可能 hang 住 | 低 |

### 已知不做的（架构决策）

| 不做项 | 原因 |
|--------|------|
| Redis 分布式限流 | 单实例内存计数器够用；多副本部署时换 Redis（见 Wave 2+） |
| 多模态（图片/语音） | F5 多模态不在 scope（见 AGENTS.md PRD §14） |
| NL2SQL 数值聚合 | RAG 不适合数值计算，需独立 NL2SQL 模块 |
| HTTPS | 内网 HTTP 部署（见 enterprise-wave-plan.md §3） |

---

## 12. 测试指引

### 单元测试

| 测试目标 | 命令 | 关键断言 |
|----------|------|---------|
| `async_retry` | `python -m pytest tests/ -k test_async_retry` | 重试 3 次成功、重试耗尽抛错 |
| 熔断器状态机 | `python -m pytest tests/ -k test_circuit_breaker` | CLOSED→OPEN→HALF_OPEN→CLOSED |
| 降级阶梯 | `python -m pytest tests/ -k test_degradation` | L0→L4 映射正确、冷却窗口生效 |
| 限流 | `python -m pytest tests/ -k test_rate_limit` | 30/hr 超限 429 |

### 集成测试

| 测试场景 | 方法 | 预期 |
|----------|------|------|
| embedding API 超时 | mock 返回 `asyncio.TimeoutError` | 重试 2 次后熔断器打开 |
| LLM 断连重试 | mock 第一次抛异常，第二次成功 | `retry_stream` 重连后正常输出 |
| 降级 L4 短路 | 打开 2 个熔断器后调用 `/ask` | 返回 degradation_message，不调 LLM |
| 限流降级联动 | L1 下降级后发 20 条消息 | 第 16 条开始 429 |

### 人工验收

```
1. docker compose build api && docker compose up -d api
2. curl http://localhost:8000/health
   → 确认 degradation.breakers 三个都是 closed
   → 确认 degradation.level 是 0
3. 正常对话: POST /ask/chat → 返回 SSE token + citation
4. 模拟降级: 手动修改熔断器阈值 → 触发打开
   → 再次 /health → level != 0
   → 对话 → 返回 degradation_message
```
