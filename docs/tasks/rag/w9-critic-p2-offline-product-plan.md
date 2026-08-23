# W9 P2 — Offline Critic Product Experiment Plan

## 目标与范围

在 P1 的默认关闭控制面上，离线注入冻结 critic transport，测量产品如何执行其动作；本计划不测量 critic/模型的语义判断质量。

输入分母固定为 P0 的 12 个 case、哈希和动作分布。注入报告与 P0 oracle 分离，且生产调用只接收注入的 `CriticResult`。

## 里程碑与验收

1. 冻结完整性：12 个唯一 case ID、输入/contract 绑定、动作分布 `5/3/2/1/1`，无 oracle 字段泄漏到 injector。
2. 产品边界：以外层 `_stream_generation_phase` 消费注入的 critic 输出；只替换 token/provider 等不确定外部依赖。
3. 停止与报告：任何必须改变运行时语义的 frozen action 标记 `PRODUCT_CONTROL_PLANE_FAILURE`、`PARTIAL`，不继续把未执行分母或恒定策略写成通过。

验收命令见实施文档；必须无模型调用、无默认开关变更、无 runtime diff。

## 风险与停止条件

- deterministic recommendation 的产品执行条件与冻结 action 不相容；记录第一失败阶段，不修改运行时。
- 未经真实产品入口覆盖的 case 不得写为 PASS。
- 任一发现需要 P1b 语义修复、修改 golden 或调用外部模型时停止。

## 不做

- 不调优 prompt，不启动 LM Studio，不运行云模型；
- 不修改 `agent/stream.py`、`agent/runtime.py`、P0 fixtures 或 golden；
- 不开始 P3。
