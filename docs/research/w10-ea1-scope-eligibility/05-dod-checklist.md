# 05 — DoD checklist（进入后续 I 的门禁）

> 本窗 = 协议设计。下面的「可进入 I」指 **measurement harness / eval runner** 另窗，不是产品 C12 修复窗，也不是 P2-R1 解阻。

## 本窗（E-A1 设计）完成定义

本窗在以下全部为真时结束：

- [x] 目录 `docs/research/w10-ea1-scope-eligibility/` 可导航
- [x] 产品路径按现网模块写清
- [x] 资格规则区分 valid product-path vs harness-only
- [x] 说明 C12 类注入为何不能当产品路径测量
- [x] Oracle：C01–C11 保持；C12 默认 `INVALID_FOR_PRODUCT_PATH_EXECUTION`
- [x] 计分契约：final citation ⊆ allowed scope
- [x] 写明 **不改变产品行为**、**不解阻 P2-R1**
- [x] 无 backend / runtime / 模型 / PR

（勾选表示**设计交付物**存在，不表示测量已跑。）

## 后续 I 允许开始的前提（measurement only）

必须全部满足，才允许打开 **harness / scorer 实现** 窗（仍零产品隔离补丁，除非独立 plan 证明产品路径 bug）：

| # | 门 | 说明 |
|---|---|---|
| D1 | 所有权 | 实施者引用 Direction A；不把 Critic 当隔离 owner |
| D2 | 入口 | 产品分母调用真实 `AgentToolScope` + `prepare_agent_generation`；禁止 `execute_frozen_case` 注入进分母 |
| D3 | C12 标签 | 实现前静态分类已是 INVALID；代码不得改成 eligible 除非 `03` 的新契约窗已完成 |
| D4 | Scorer | 实现 `04`（含禁止 body-diff-only）；E-A2 可与 harness 同窗，但契约不得缩水 |
| D5 | 分母 | C01–C11 为产品分母；C12 计入 invalid 计数，不计入 pass_rate 分母 |
| D6 | 探针隔离 | DEFENSE_IN_DEPTH_PROBE 若保留，独立 artifact，不得覆盖独立复核 |
| D7 | 冻结文件 | 不静默改 `w9-critic-capability-contract.json` / cases evidence |
| D8 | 模型 | 该 I 仍可 **零模型**（确定性 control plane）。需要 LLM 的窗必须另开 |
| D9 | P2-R1 | PR/文档仍写 **BLOCKED**，直到独立复核定义的解阻条件满足（见下） |
| D10 | 产品代码 | 默认 **不**改 `stream.py` merge / `gate_agent_chunks` / Critic 签名（那是 B；E-B0 之后） |

## 本协议明确 **不解阻** P2-R1

解阻 P2-R1 至少还需要（均未在本窗发生）：

1. 产品分母 12 案均有诚实资格：**要么** C12 有冻结的新产品路径 oracle 且可映射，**要么** 程序明确把冻结套件改为 11 案并接受「C12 永久 INVALID」（后者须单独程序决策，本协议 **不**做该决策）。
2. Scorer 满足 `04`，且无 F3 false pass。
3. 独立复核 artifact 更新，且不把旧注入失败写成产品 FAIL。
4. 仍无「用 11/11 宣称 12/12 PASS」。

**在此之前：P2-R1 remains BLOCKED / `MEASUREMENT_PROTOCOL_MISMATCH`。**

## Threats to validity（效度威胁）

| 威胁 | 为何严重 | 缓解 |
|---|---|---|
| T1 Harness vs product path | C12 主证据是注入（H1） | 分母禁止注入；资格预检 |
| T2 11/11 外推 | 有效案全过 ≠ 套件 PASS | invalid 计数保留 C12 |
| T3 Oracle 贴纸 | 空 plan 当成 SCOPE_VIOLATION | `03` M4 |
| T4 正文 diff | 已产生 false safe | `04` 禁止 |
| T5 打非终态 | 候选 citation / critic chunks | 只打 done 对齐列表 |
| T6 None vs empty scope | 误伤全可见或漏全拒绝 | `04` F7 |
| T7 H2 当 CVE | merge 缺口仅非法输入下 PROVEN | 探针标签；E-B1 才问可达性 |
| T8 H3 当产品 bug | 接口表达不了冻结 provenance | 保持 INVALID，不扩 Critic |
| T9 测了即改产品 | 「顺手」merge 过滤 | D10；B 走 E-B0 |
| T10 本协议当解阻 | 文档被抄进 progress 当 PASS | README / 本页钉死 BLOCKED |
| T11 对等案扩大化 | 把 Hit@3 / 其它 golden 当 C12 同类 | `03`：仅本 12 案；仅 C12 foreign-only |
| T12 模型污染 | 用 LLM 判断资格 | 静态算法 |

## 明确声明

1. **本协议不改变产品行为。** 无 flag、无 merge 过滤、无 Critic 接口变更。
2. **本协议不解阻 P2-R1。** 状态仍为 BLOCKED。
3. **本协议不声称 C12 是产品路径失败。** 声称的是：在 Direction A 下它当前 **不能** 作为产品路径执行测量。
4. **本协议不声称资格已在 CI 中「证明完毕」。** 分类规则已写；执行器 I 尚未做。

## 后续 I 建议验收（实现窗复制，本窗不跑）

```text
# 静态：C12 资格（无模型）— E-A2 已实现：
# pytest tests/test_w10_ea2_scope_eligibility.py -q
# 期望：C12 product_path_eligible is False
# C01–C11 product_path_eligible is True
# C12 classification INVALID_FOR_PRODUCT_PATH_EXECUTION
# C12 不进入 pass_rate 分母
```

E-A1 设计窗 **不**把上述命令当作已绿验收。E-A2 测量窗应跑 `backend/tests/test_w10_ea2_scope_eligibility.py`。

## Stop

E-A1 **设计**到此结束。下一窗若做 I，只做测量适配器 + 本契约 scorer，或做显式契约冻结；不要做 Direction B 产品补丁，不要改 cockpit 声称 P2-R1 已解阻。
