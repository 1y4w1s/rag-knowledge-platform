# W9 P2b — C11 修订执行器闭环

## 范围

只关闭冻结 P2 所暴露的 C11 控制面缺口：`rules_v1` 产出的合法
`REVISE_FROM_EXISTING_EVIDENCE` 必须被既有的单一外层编排者执行。

不重跑完整 P2，不变更冻结 P2 证据，不调优 prompt/模型，不增加检索、循环、状态模型或运行时 rollout。

## 根因与最小修复

`_stream_generation_phase` 的既有有界修订执行器同时承担共享 deadline、一次预算、轨迹、审计、复核及最终输出边界；它却额外限定 `critic_result.method == llm_verify_v1`。这使动作语义被判断方法覆盖，`rules_v1` 的 C11 动作落入 `skipped_unavailable`。

移除该方法门槛，其余执行器条件与实现不变：动作仍必须是 `REVISE_FROM_EXISTING_EVIDENCE`、修订次数仍小于 1；修订仅传入现有 gated chunks；成功候选仍须经 post-revision critic 验证后才输出。

## 验收

- C11 `rules_v1` 路径执行一次修订、检索次数为 0、复用既有 chunks，且审计与轨迹有记录；
- deadline、执行器失败、预算已耗尽均安全终止且无重试放大；
- `llm_verify_v1` 修订、`RETRIEVE_MISSING_EVIDENCE` 与 critic 默认关闭回归保持有效；
- `w9-critic-p2-offline-product.json` 仍保留 `PARTIAL` 与 C11 的历史 `skipped_unavailable`；
- 新 P2b artifact 单独记录修复后 PASS；不代表 W9 P2 PASS 或 P3 就绪。

## 验证命令

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest tests/test_critic_w9_p2b_c11_remediation.py tests/test_critic_w9_offline_product.py tests/test_critic_w9_control_plane.py tests/test_critic_w9_recovery.py tests/test_critic_w9_actions.py tests/test_critic_w9_terminal.py tests/test_agent_l3_critic.py -q
..\.venv\Scripts\python.exe -m ruff check app/services/agent/stream.py tests/test_critic_w9_p2b_c11_remediation.py
git diff --check
```
