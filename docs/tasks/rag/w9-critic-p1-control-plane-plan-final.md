# W9 P1 — Critic 控制面加固规划

> 日期：2026-08-24
> Base SHA：`cc3321e7a768426f7d7d665984dfbcba6140bf9f`
> 边界：CPU / deterministic / mocked；不运行模型、不调 prompt、不做 rollout。

## 目标

本阶段只关闭 W9 P0 的架构阻塞，使 critic/recovery 具备单一 owner、显式预算、canonical trajectory、EvidenceState/审计/耗时可见性，并让语义 critic 校验真实最终候选。

P1 仅在下列条件全部满足时 PASS：

- Agent critic 推荐动作由 `_stream_generation_phase` 在 `_stream_agent_core` 下唯一编排；
- critic 只返回 report / recommended action，不自主执行 retrieve、revise 或 re-critic；
- 每次 action 受 agent step、absolute deadline 和 critic revision/revalidation 预算约束；
- 成功、失败、越权、预算耗尽与 deadline 耗尽均进入同一 trajectory / audit；
- recovery evidence 经过 tool scope、EvidenceState reducer 与 matcher；
- critic ON 时 Fast/Agent 都只发布并持久化最后冻结候选；
- 现有 flags 保持默认关闭，OFF 路径行为不变。

## 不做

- 不运行 LM Studio、云模型 benchmark 或真实本地测量；
- 不修改 critic prompt、模型、temperature 或 capability oracle；
- 不新增 `CriticRuntime`、平行 EvidenceState 或 shadow history；
- 不修改检索算法、切片、embedding、golden 数据或默认开关；
- 不做 runtime rollout；不提前执行 W9 P2。

## 里程碑

1. 冻结 P1 machine-readable artifact 与 12 个架构行为门禁。
2. 把 critic retrieval 接入 canonical step / EvidenceState / audit / latency / deadline。
3. 分离 critic judgment 与 outer action，并记录有序 `critic_actions`。
4. 把 Fast/Agent critic-ON 路径收敛到 buffered final-candidate boundary。
5. 跑 critic、reflection、runtime、finalize、citation、evidence、audit 回归及 Ruff。

## DoD

- artifact 的 zero-tolerance counts 全为 0；
- 12 类行为均绑定并通过 deterministic/mocked tests；
- 默认 OFF 回归通过；Golden diff = 0；workflow diff = 0；LM Studio = NO；
- `READY_FOR_OFFLINE_PRODUCT_EXPERIMENT=YES`；
- `READY_FOR_REAL_LOCAL_MEASUREMENT=NO`，`RUNTIME_ROLLOUT=NO`。
