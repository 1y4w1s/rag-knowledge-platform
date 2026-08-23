# W9 P2-R1 — 冻结 12-case 离线产品边界复测

## 范围与门禁

在 PR #55（merge `0609f2251d6d78bef5a8ce8826aa1fbf42da8020`）之后，使用既有
`w9-critic-cases.json`、`w9-critic-capability-contract.json` 与
`w9-critic-p2-injected-reports.json` 的 12 个冻结 case，重新测量 Critic 推荐动作经过
Agent hardened orchestration boundary 后的产品行为。

本阶段只新增测试、测量 harness、独立结果 artifact 与状态记录；不修改产品运行时代码、冻结输入、
oracle、旧 P2 `PARTIAL` artifact、默认开关或 workflow，不执行任何本地/外部模型。

执行顺序固定为 C01→C12。若出现新的 `PRODUCT_CONTROL_PLANE_FAILURE` 或其他产品语义缺陷，立即停止，
其余 case 标记为 `NOT_EXECUTED_AFTER_STOP_CONDITION`，冻结 `VALID / PARTIAL`；只有纯粹且无歧义的
`HARNESS_INTEGRATION_FAILURE` 才允许先经独立审查后修复 harness 并继续。

## 实现文件

- `backend/tests/w9_critic_p2_r1_harness.py`：加载冻结输入，以注入 CriticResult 驱动真实产品编排边界；
  provider、数据库写入与底层检索结果使用确定性替身，编排、预算、轨迹、EvidenceState、终态逻辑不 mock。
- `backend/tests/test_critic_w9_p2_r1_offline_product.py`：校验冻结输入完整性、逐 case 观测、staged contract、
  stop rule、C11 回归、聚合指标和 anti-degenerate controls。
- `backend/tests/fixtures/l4_critic/w9-critic-p2-r1-offline-product.json`：新一轮独立冻结结果；永不覆盖旧 P2。
- `docs/status/progress.md` / `docs/remaining-plan.md`：仅在结果冻结后同步简明状态与下一门禁。

## 测量协议

每个 case 记录 critic method、推荐/观测动作、执行状态、recovery/retrieval/revision 次数、EvidenceState、
trajectory、audit、budget、scope/provenance、terminal、safe outcome、`first_failed_stage`、classification 与 pass。
失败阶段按 L0→L8 首个失败冻结。12 case 全部完成后才运行 ALWAYS_ACCEPT / ALWAYS_REVISE /
ALWAYS_RETRIEVE / ALWAYS_CLARIFY / ALWAYS_REFUSE 控制；常量策略不得获得 perfect result。

## 验收

```powershell
cd backend
$w9Jwt=(Get-Content -LiteralPath ..\.env | Where-Object { $_ -like 'JWT_SECRET=*' } | Select-Object -First 1).Substring(11); $env:JWT_SECRET=$w9Jwt
.\.venv\Scripts\python.exe -m pytest tests\test_critic_w9_p2_r1_offline_product.py tests\test_critic_w9_p2b_c11_remediation.py tests\test_critic_w9_offline_product.py tests\test_critic_w9_control_plane.py tests\test_critic_w9_recovery.py tests\test_critic_w9_actions.py tests\test_critic_w9_terminal.py tests\test_agent_l3_critic.py -q
.\.venv\Scripts\python.exe -m ruff check tests\w9_critic_p2_r1_harness.py tests\test_critic_w9_p2_r1_offline_product.py
git diff --check
```

## 冻结结果（2026-08-24）

- 结果：`VALID / PARTIAL / FROZEN`；冻结 denominator 12，执行 12，通过 11，invalid 0。
- 首个产品失败：`C12-out-of-scope-provenance`；首败阶段
  `L6_BUDGET_SCOPE_PROVENANCE_CORRECT`；分类 `PRODUCT_CONTROL_PLANE_FAILURE`。
- 观测：C12 完成一次 bounded retrieval 与一次 revision/revalidation 后，post-recovery critic 输入仍同时包含
  新的 allowed-kb chunk 与冻结输入中的 foreign-workspace/foreign-kb chunk。
- 安全：safe outcome 12/12，unsafe accept 0，hidden/unaccounted recovery 0；未发生未经复核的 post-critic mutation。
- C11：`rules_v1` 正常执行；revision 1、retrieval 0、轨迹/审计/预算/终态均通过；旧 P2 的
  `skipped_unavailable` 历史保持不变。
- Anti-degenerate controls：因 C12 产品 stop condition，按协议 `NOT_RUN_PRODUCT_STOP_CONDITION`。
- 产品运行时改动 0；Golden diff 0；workflow diff 0；外部模型执行 NO；runtime rollout NO。

结果 artifact：`backend/tests/fixtures/l4_critic/w9-critic-p2-r1-offline-product.json`。

通过口径严格使用 mission 的 P2-R1 PASS gate；若未满足，不得宣称 PASS、P3 ready 或任何模型能力。
