# 03 — Claim restrictions（禁止声称）

> 本文件优先级高于任何「顺口总结」。进度 / cockpit / PR / 面试口播均须遵守。

## 1. 硬禁止（MUST NOT）

### 1.1 声称生成质量（在测量之前）

**禁止**写出或暗示：

- 「生成质量 PASS / 回答已接地 / faithfulness 达标」
- 「P0 引用溯源对话已用本协议验过」（PRD §2.1 要的是终态；本窗只冻结如何观察，**未执行**）
- 「四靶已有通过率 / 基线分数」

本窗交付物 = **协议**，不是 run result。

### 1.2 声称 Critic 能力

**禁止**从本协议或未来 generation observation 结果外推：

- Critic oracle capability / 语义 Critic PASS
- Critic 默认 ON / 生产 rollout
- 用 `w9-critic-capability-contract.json` 的 `expected_action` 当生成质量金标

E-A4/E-A5 已把 `Critic oracle capability` 列入 forbidden；本协议 **继承并加强**：生成观察 ≠ Critic 观察。

### 1.3 与 E-A5 结果合并 / 混写

| E-A5（L0） | E-B1（本协议 · L1 观察点） |
|---|---|
| `observation_point=plan_construction_citations` | `observation_point` 草案 = `generation_final_content_and_citations`（见 `05`） |
| 声称：`plan-construction citation scope compliance` | **尚无**允许的 generation 正式声称（未跑） |
| 结果文件：`w10-ea4-formal-window-result.json` | **禁止**向该文件写入 generation 字段或改写 `asserted` |
| 分母语义：plan citations ⊆ scope | 分母语义：生成后 `content`/`citations` 四靶 |

**禁止：**

- 把 E-A5 `11/11` 与「生成观察」写成同一通过率
- 把 `scope_compliance_pass=true` 改述为「终态引用安全」
- 用 E-A5 artifact 的 `measurement_valid=true` 为 generation 背书
- 新结果覆盖或 silently extend E-A5 reserved 文件

一句话：

> **plan-construction citation scope ≠ post-generation observation。**

---

## 2. 继承的禁止声称（来自 E-B0 / E-A4，仍有效）

- P2-R1 unblocked / 12/12 产品 PASS  
- C12 进入产品路径分母或贴 SCOPE_VIOLATION 产品 PASS  
- Hit@3 绿 ⇒ RAG 端到端 / 生成绿  
- H2 / 污染 `gated_chunks` 已证成 CVE  
- 可开始 remaining-plan「W10 Multimodal Vertical Slice」或 Critic 默认 ON  

---

## 3. 本窗允许写进进度的话（仅此）

允许声称字符串（文档状态，非测量）：

```text
W10 E-B1 generation observation protocol frozen
```

允许附带说明：

- 观察窗口 = After：`state["content"]` + `state["citations"]`；Before 对照 = `gen_plan`
- 四靶已定义、**未测量**
- 不改变 E-A5 / control-plane / P2-R1 BLOCKED

---

## 4. 本窗非目标（已遵守）

- 不改 `backend/app`
- 不调用 DeepSeek / 通义 / 嵌入 / 本地 GGUF / 任何 eval 生成
- 不跑 `_stream_generation_phase` 或 generation pytest
- 不新建正式 generation run JSON
- 不实施 Decision DiD E-B0/E-B1
- 不把 W9 Critic 12 案改写成新产品 case（仅做资格研究）

---

## 5. 唯一推荐下一窗

**名称：** W10 E-B2 — Generation observation reserved artifact schema freeze（test-only）  

**类型：** 调研/契约 · 建议思考强度 **medium**  

**严格只做：** 对标 E-A4：把本目录 `05-artifact-schema-draft.md` 收成 **test-only** 模块 +（可选）`docs` 旁 schema 镜像；冻结新 `protocol_version` / `artifact_schema_version` / `observation_point` 常量与 **forbidden claims**；**零 LLM**；**不写**正式 observation 结果；**不覆盖** `w10-ea4-formal-window-result.json`。

**不做：** 生成执行 · 产品 runtime · Critic · P2-R1 解阻 · Multimodal · DiD 探针 · 把 mock `[片段N]` 绿写成 grounding PASS。

**验收示例（E-B2 窗，非本窗）：**

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
.\.venv\Scripts\python.exe -m pytest tests/test_w10_eb2_generation_observation_contract.py -q
```

（若 E-B2 仍选纯文档，则以该窗 README DoD 勾选代替；**不得**用 `test_retrieval_golden.py` 或 E-A5 重跑验收。）

**备选（一句）：** 仅当 owner 书面要求先补分母时，改为「空检索 / 拒答 eligible fixture **研究**」（仍零 LLM、不实施产品 case）。

## Stop

E-B1 协议到此结束。不得在本窗续写 E-B2 实现。
