# 步骤 2 详细计划：CI 真实嵌入 job + 检索降级修复

> 基于 2026-07-19 全系统诚实性审查结果
> 原则：CI 门禁用真实嵌入检验语义检索；检索链路嵌入失败时降级为纯 FTS

---

## 问题 A：CI 不测语义检索

### 三层 mock 叠加

| 层 | 文件 | 行为 |
|----|------|------|
| 1 | `conftest.py:129-136` | autouse fixture，设 `RAG_REAL_EMBEDDING=1` 可跳过 |
| 2 | `test_retrieval_golden.py:65-68` | 无条件 monkeypatch embed_texts，**不检查环境变量** |
| 3 | `ci.yml:65-68` | `continue-on-error: true`，RAG 测试失败不阻断 CI |

### 修复 A：3 个文件

#### A1: `test_retrieval_golden.py` 第 65-68 行

```python
# 改前：无条件 mock
@pytest.fixture(autouse=True)
def _mock_embedding(monkeypatch):
    monkeypatch.setattr(embedder, "embed_texts", _mock_embed_texts)

# 改后：设 RAG_REAL_EMBEDDING=1 时跳过 mock
@pytest.fixture(autouse=True)
def _mock_embedding(monkeypatch):
    import os
    if os.environ.get("RAG_REAL_EMBEDDING") == "1":
        return
    monkeypatch.setattr(embedder, "embed_texts", _mock_embed_texts)
```

**原理**：与 `conftest.py` 协定一致。环境变量控制是否 mock。

#### A2: `ci.yml` 新增 `rag-real-embedding` job

在 `test` job 之后新增：

```yaml
rag-real-embedding:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: test
    services:
      postgres:
        image: pgvector/pgvector:pg16
        # ... 同 test job
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11", cache: "pip" }
      - run: pip install -r backend/requirements.txt
      - run: cd backend && alembic upgrade head
      - name: Run retrieval tests with real embeddings
        env:
          RAG_REAL_EMBEDDING: '1'
        run: |
          cd backend
          python -m pytest tests/test_retrieval_golden.py -v --tb=short
```

**要点**：
- `needs: test` → 基础测试先过再跑
- `RAG_REAL_EMBEDDING=1` → 绕过两层 mock
- **无 `continue-on-error: true`** → 失败阻断 CI
- 只跑 `test_retrieval_golden.py` → 不依赖 DeepSeek API
- fastembed 在 `requirements.txt` 中，CI runner 无需额外安装

#### A3: `conftest.py` 第 129-136 行

**无需修改**。已有 `RAG_REAL_EMBEDDING` 检查。

---

## 问题 B：检索链路嵌入失败不降级

### 故障场景

```
embed_texts() → fastembed 加载失败 / ONNX 崩溃 / 模型缺失
        ↓
async_retry 重试耗尽
        ↓
熔断器 OPEN（5 次失败后）
        ↓
下一请求 → async_retry 不重试 → 抛出异常
        ↓
retrieve_chunks 未捕获 → HTTP 500
        ↓
用户看到错误页面
```

**对比：文档入库链路做对了**

```
try_embed_texts() → 返回 None → vectors=[] → 入库 FTS-only ✅
```

### 修复 B：1 个文件，3 行核心改动

#### B: `retrieval.py` 第 82 行附近

```python
# 改前
query_vec = (await embed_texts([query]))[0]

# 改后
from app.core.degradation import assess_degradation, degradation_requires_embed

if degradation_requires_embed(assess_degradation()):
    query_vec = (await embed_texts([query]))[0]
else:
    query_vec = None  # 触发纯 FTS 兜底
```

**原理**：
- `assess_degradation()` 检查三个熔断器状态（LLM/Embed/Rerank）
- `degradation_requires_embed()` 返回当前等级是否需要嵌入
- L3 以下：正常调用 `embed_texts()`
- L3（EMBED_DOWN）及以上：跳过向量召回，走纯 FTS
- 熔断器自身的 HALF_OPEN 自动恢复仍然工作

---

## 改动清单

| 文件 | 改动量 | 性质 |
|------|--------|------|
| `test_retrieval_golden.py` | +4 行（加环境变量检查） | 修复 |
| `ci.yml` | +35 行（新增 job） | 新增 |
| `retrieval.py` | +3 行核心 + import | 修复 |
| `conftest.py` | 0 行（已有协定） | 不变 |

---

## 验证标准

| 测试 | 方法 | 预期 |
|------|------|------|
| mock 测试仍通过 | `pytest test_retrieval_golden.py`（无环境变量） | 30 秒内通过 |
| 真实嵌入测试通过 | `RAG_REAL_EMBEDDING=1 pytest test_retrieval_golden.py` | ~10 分钟，109 题全部通过 |
| 嵌入失败降级 | 模拟 fastembed 崩溃 + 检索 | 不走向量召回，FTS 返回结果 |
| CI 新 job 语法正确 | `act` 或 push 验证 | yaml 解析无错误 |

---

## 回滚方案

| 问题 | 回滚操作 |
|------|----------|
| CI job 耗时太长 | 删 `ci.yml` 中 `rag-real-embedding` job |
| 降级修复引入 bug | 恢复 `retrieval.py` 的 `embed_texts` 裸调用 |
| fastembed 在 CI runner 上不兼容 | 暂时保留 mock job，等修复后再加 real job |
