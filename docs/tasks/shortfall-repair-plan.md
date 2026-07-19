# 短板修复计划（2026-07-18）

>源自 [架构评估](../AGENTS.md) 发现的三项核心短板。
>实施顺序：Phase 1（P0 拒答）→ Phase 2（P1 多轮对话）→ Phase 3（P1 前端测试）

---

## Phase 1：修复拒答率 0%（P0 — Bug 1+2+3） ✅ 2026-07-18

### 状态：全部完成 ✅

修改文件：
- `backend/tests/benchmark/adapters/generation.py` — 增加 filter_relevant_chunks + should_refuse_answer 门控
- `backend/app/services/rag/engine.py` — 增加 should_refuse_answer 门控 + _expand_and_retry 过滤
- `backend/tests/benchmark/tests/run_golden_full.py` — 修复拒答题评估逻辑
- `backend/app/services/rag/relevance.py` — 恢复 _vector_scores_universally_weak
- `backend/tests/test_rag_relevance.py` — 增加 3 个系统级拒答集成测试

验证：
- test_rag_relevance.py: 14/14 ✅
- test_retrieval_hybrid.py: 6/6 ✅
- test_citations.py: 4/4 ✅
- test_generation.py: 19/19 ✅
- test_retrieval_golden.py: 拒答题 GQ-36/37/38 ✅

---

## Phase 2：修复多轮对话 Bug + 补齐缺失项（P1）

### 2.1 Bug A：workspace 路径重复检索+双重保存 ✅ 已修复
### 2.2 Bug B：KB flat chat 端点支持 thread_id ✅ 已修复
### 2.3 接线重新生成（regenerate）功能 ✅ 已修复
### 2.4 增加 token 计数与上下文窗口动态管理 ✅ 已修复
### 2.5 回归：多轮对话端到端测试 ⏳ 待做

### 背景

Golden QA 38 道拒答题（`expect_rejection: true`）全部失败，拒答准确率 0.0%。
三个独立 Bug 叠加导致：

1. **Bug 1（致命）**：`benchmark/adapters/generation.py` 完全不调用 `filter_relevant_chunks()` / `should_refuse_answer()`，不相关 chunk 直接喂 LLM
2. **Bug 2（致命）**：`engine.py` 导入了 `should_refuse_answer` 但从未调用，只靠 `if not chunks:` 判断（但向量检索永远有结果）
3. **Bug 3（促成因）**：`run_golden_full.py` 评估逻辑因空 `expect` 字段导致 `ok` 永真

### 1.1 修复 Bug 1：benchmark GenerationAdapter

**文件**：`backend/tests/benchmark/adapters/generation.py`

- `generate()` 中 `retrieve_chunks()` 之后增加：
  - `filter_relevant_chunks(chunks, query)` 过滤
  - `should_refuse_answer(filtered_chunks, query)` 判定
  - 应拒答 → 返回 `no_context_reply_for(query)` + 空 citations

### 1.2 修复 Bug 2：ChatEngine._generate()

**文件**：`backend/app/services/rag/engine.py`

- `_generate()` 中增加 `should_refuse_answer(self.chunks, self.query)` 调用
- 拒答时直接流式输出 `no_context_reply_for`，跳过 LLM

### 1.3 修复 Bug 3：run_golden_full.py 评估逻辑

**文件**：`backend/tests/benchmark/tests/run_golden_full.py`

- 当 `expect_rejection=True` 且 `expect` 为空字典时
- 直接判定 `ok = False`（期望无匹配），而非空条件默认真

### 1.4 回归验证

- `test_retrieval_golden.py` 全量通过（含 38 道拒答题）
- `test_rag_relevance.py` 无退化

### 1.5 补充系统级拒答集成测试

- `test_retrieval_golden.py` 增加端到端拒答测试
- 上传文档 → 检索 → 验证拒答

---

## Phase 2：修复多轮对话 Bug + 补齐缺失项（P1）

### 背景

多轮对话基础设施完整（模型+持久化+API端点+前端UI），但有两个 Bug 导致生产路径无法正常工作。

### 2.1 修复 Bug A：workspace 路径重复检索+双重保存

**文件**：`backend/app/services/rag/chat.py`

- `stream_workspace_chat_events` 中删除 engine.stream() 之后约 50 行重复代码
- Engine 已执行完整 _load_history → _retrieve → _generate → _save 链路

### 2.2 修复 Bug B：KB flat chat 端点支持 thread_id

**文件**：`backend/app/schemas/chat.py` → `ChatRequest` 增加 `thread_id` 可选字段
**文件**：`backend/app/api/chat.py` → `stream_chat_events` 路由接收 `thread_id`

### 2.3 接线重新生成（Regenerate）

**文件**：`frontend/src/pages/ChatPage.tsx`、`frontend/src/pages/AskPage.tsx`

- 实现 `onRegenerate` 回调
- 删除最后一条 assistant 消息 → 用同一 thread 重新发送上一条 user 消息

### 2.4 增加 token 计数与上下文窗口管理

**文件**：`backend/app/services/rag/generation.py`

- 增加 `estimate_token_count()`（字符 ≈ token 估算）
- `build_messages()` 动态裁剪 history，保留 60% context window 给检索片段

### 2.5 回归测试

- 增加 `test_chat_multi_turn.py`
- 模拟 3 轮连续对话 → thread 创建 → 历史注入 → regenerate

---

## Phase 3：前端测试补齐（P1）

### 状态：部分完成（3.1~3.2 ✅，3.3~3.5 ⏳）

### 背景

127 个 TSX 文件，原仅 10 个测试文件（79 用例），0 页面测试，~6% 组件覆盖。

### 3.1 补齐 thread-api 模块测试 ✅

`frontend/src/lib/thread-api.test.ts`（14 tests）：create/list/get/delete thread、streamThreadChat SSE 解码、deleteThreadMessage、mock fetch URL 验证。

### 3.2 补齐 useThreadSession hook 测试 ✅

`frontend/src/lib/use-thread-session.test.ts`（5 tests）：renderHook 测试返回值完整性、sendMessage/regenerate 委托、createNewThread 调用、初始状态。

### 3.3 补齐 ChatPage / AskPage 核心交互测试 ✅

`frontend/src/components/chat/ChatPageShell.test.tsx`（7 tests）：渲染 thread panel/message list/input、loading 状态、消息展示、regenerate 回调、新建对话、错误展示、input disabled。

### 3.4 补齐 AuthGuard / ProtectedRoute 权限测试 ✅

`frontend/src/components/auth/ProtectedRoute.test.tsx`（4 tests）：已登录渲染 Outlet、未登录跳转 /login、redirect 参数传递、search params 保持。

### 3.5 CI 增加前端测试 job ✅

`.github/workflows/ci.yml`：`lint` job 中 build 后增加 `npm test` 步骤。

### 总结果

| 指标 | 原始 | 最终 | 增长 |
|------|------|------|------|
| 测试文件 | 10 | 14 | +4 |
| 测试用例 | 79 | 109 | +30 |
| 覆盖范围 | API + 6组件 | + thread-api + hooks + ChatPageShell + ProtectedRoute | |

### 3.5 CI 增加前端测试 job

`.github/workflows/ci.yml` 增加 `frontend-tests`

---

## 实施顺序

```
Phase 1（1.1 → 1.2 → 1.3 → 1.4 → 1.5）
  ↓ 确认拒答题全过
Phase 2（2.1 → 2.2 → 2.3 → 2.4 → 2.5）
  ↓ 确认多轮可用
Phase 3（3.1 → 3.2 → 3.3 → 3.4 → 3.5）
```

**预期**：3 轮对话完成全部 3 个 Phase。
