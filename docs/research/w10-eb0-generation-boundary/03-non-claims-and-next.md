# 03 — Claims we MUST NOT make · 下一窗

## L0 成功 **禁止**写出的声称

E-A5 11/11 与 `measurement_valid=true` **只**支撑允许声称：

```text
plan-construction citation scope compliance
```

（见 `w10-ea4-formal-window-result.json` → `measurement_claims.asserted`。）

| 禁止声称 | 为何 L0 不能支撑 |
|---|---|
| 「生成质量 PASS / 回答已接地」 | 无 `assistant_content`；未调用 L1 |
| 「generation-final safety PASS」 | 观察点不是 `state["citations"]`；E-A4 已列入 forbidden |
| 「P0 引用溯源已测过」 | PRD §2.1 要的是**对话终态**引用；E-A5 是 plan 快照 |
| 「无依据不会胡编」 | 未做 unsupported-claim 评分；keep-all 甚至可能给胡编正文配满引用 |
| 「该拒会拒、不该拒不拒」 | 无空检索 eligible 案；C07 在 L0 为 `plan_refusal=false` |
| 「P2-R1 unblocked / 12/12 产品 PASS」 | artifact 钉死 `BLOCKED`；C12 仍 INVALID |
| 「Critic oracle / 语义能力 PASS」 | 未跑 Critic；禁止从 E-A5 外推 |
| 「11/11 ⇒ 可外推 12/12」 | E-A1 T2 stop rule；C12 不在分母 |
| 「Hit@3 绿 ⇒ RAG 端到端绿」 | golden 只测检索 |
| 「产品隔离已用生成终态闸门加固」 | `gate_agent_chunks` / align **仍不**接收 `AgentToolScope`（E-A1 `04`）；L0 11/11 是 plan-front **推论**的测量，不是 Direction B |
| 「H2 / 污染 gated_chunks 是 CVE」 | 未做生产可达性；Decision H2 仅探针 |
| 「可以开始 W10 Multimodal / Critic 生产默认 ON」 | remaining-plan 多模态项 ≠ 本 W10；Critic 默认关仍有效 |

进度、cockpit、PR、面试口播若提到 E-A5，必须带观察点全名：**plan-construction citation scope**，不得省略成「W10 评测过了」。

## 本窗非目标（已遵守）

- 不改 `backend/app`
- 不新增 / 不跑 generation pytest
- 不调用 DeepSeek / 通义 / 本地 GGUF / 任何 eval 生成
- 不改写 `w10-ea4-formal-window-result.json`
- 不实施 DiD merge 过滤、不改 Critic 签名
- 不把 Decision 的 E-B0（DiD）与本 E-B0（生成边界）合并成一个 Implement

## 唯一推荐下一窗：E-B1

**名称：** W10 E-B1 — Generation-final observation protocol freeze  

**类型：** 调研/设计 · 建议思考强度 **high**  

**严格只做：** 用文档（必要时 **test-only schema**，对标 E-A4）冻结 L1 测量的观察点与四靶指标定义：计分对象 = 生成后 `align_citations_to_answer` 产出的 `state["citations"]`（及与 plan 快照的 diff 字段）；写明 keep-all 分桶、空 citation 与拒答的分母规则；声明新 `protocol_version` / 新 reserved 文件名，**不得**把 generation 声称写入现有 E-A5 结果信封。

**不做：**

- 调用 LLM 或本地推理；不写正式 generation run 结果
- 不改产品 runtime、flags、Critic 默认
- 不把 Decision DiD E-B0/E-B1、P2-R1 解阻、Hit@3、Multimodal 塞进同一窗
- 不把 mock/`[片段N]` 单元绿解释为 grounding PASS

**验收（E-B1 窗，非本窗）：** 目录 `docs/research/w10-eb1-generation-observation/`（或同等）含 allowed/forbidden claims；若有 schema 测试则纯结构、零网络。示例：

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
.\.venv\Scripts\python.exe -m pytest tests/test_w10_eb1_generation_observation_contract.py -q
```

（E-B1 若选择纯文档冻结、不写 tests，则以该目录 README DoD 勾选代替；**不得**用 `test_retrieval_golden.py` 或 E-A5 重跑当 E-B1 验收。）

**为何是这一条而不是 FE-2/FE-3 实验：** E-A3 已证明「错观察点」与 P2-R1 同族。生成平面若先跑模型，会再次把 plan 列表或 mock 绿当成终态。先钉观察点（E-A4→E-A5 的成功模式），再另窗才考虑 **零或真实** 生成执行。

**备选（一句）：** 仅当 owner 书面否决协议冻结时，才改为「零 LLM 的 L0 空检索拒答回归设计」（仍不是生成质量）。

## Direction B 残差（本窗裁定）

Decision 表 **E-B0 DiD 架构评审 / E-B1 污染探针**：**继续推迟**。A 轨 L0 未显示产品路径需要 merge 再过滤才能解释 E-A5 结果；H2 可达性仍 SPECULATIVE。生成观察点协议 **不**包含 DiD 补丁。

## Stop

E-B0 章程到此结束。下一对话只开 **E-B1 观察点协议**。
