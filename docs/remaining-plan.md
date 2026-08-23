# 索隐剩余计划

> **V1.0 程序状态（2026-08-23�?* �?[`status/v1-convergence-status-2026-08-23.md`](status/v1-convergence-status-2026-08-23.md) · **驾驶�?* �?[`cockpit.html`](cockpit.html) · **Known limitations** �?[`status/v1-known-limitations.md`](status/v1-known-limitations.md)

---

## V1.0 Convergence �?当前程序状态（2026-08-23�?

**master @** `dffcd52ff66e0726a0639e2b2739c104941d9fd0` · **阶段�?* FINALIZATION PHASE · **Runtime rollout�?* NO

### 已关�?/ 冻结能力�?

| �?| 状�?| 摘要 |
|----|------|------|
| T2 | CLOSED_FOR_V1_0 | GQ-132/149 real-validated（denom **2**）；broader NOT_MEASURABLE |
| TOOL selection | CLOSED_FOR_V1_0 | S2/S3A NO_MEASURABLE_GAIN · GQ-131 model boundary · remediation STOP |
| MEMORY | CLOSED_FOR_V1_0 | L3 10/10 · L4/L5 0/10 · C1 no gain · C2 NO_GO |
| ADVERSARIAL | FROZEN / CHARACTERIZED | P0→P5 complete · 4-strata primary **2/4** · trials **10/20** · remediation DEFER |

### 下一 V1.0 主线（active�?

1. **W9 Critic Hardening** �?NEXT
2. W10 Multimodal Vertical Slice
3. Final Frozen Benchmark
4. Feature Flag / Default / Rollout Audit
5. README / Architecture / Benchmark Report 终对�?
6. Demo / Reproducibility pass
7. V1.0 RC feature freeze
8. **v1.0.0 tag**

### 不得再列�?active V1.0 TODO

ADVERSARIAL P0–P5 · TOOL selection remediation · MEMORY remediation · T2 broadening �?仅可出现�?**Deferred / Known limitations / Post-V1.0 research backlog**�?

### Post-V1.0 backlog（非 V1.0 主线�?

MCP · Browser Agent · Multi-Agent · GraphRAG · Workflow Engine · Code Agent · General Agent Runtime

---

## 已完成的里程碑（2026-08-14 及以前完结核对）

| 里程�?| 状�?| 日期 |
|--------|------|------|
| 评分引擎 W2 重构 | �?| 2026-07-19 |
| 测试集版本化 W1 + review_signoff | �?| 2026-07-19 |
| CI 三层门禁 W4 | �?| 2026-07-19 |
| 英文嵌入 W5 | �?| 2026-07-19 |
| 测试集质量审�?P0-P2 | �?| 2026-07-20 |
| 文档清理�? 个过期文档已删） | �?| 2026-07-20 |
| C1 Enterprise/CRAG 回归叙事 | �?| 2026-07-21 |
| C2 Advanced QA 门槛 | �?| 2026-07-21 |
| C3 评分门禁可挡坏变�?| �?| 2026-07-21 |
| C4 CRAG 夜间全量 4409 | �?| 2026-07-21 |
| D1 thorough 真正多步 | �?| 2026-07-21 |
| D2 精准内自适应深度 | �?| 2026-07-21 |
| D3 工具结果进引�?拒答 | �?| 2026-07-21 |
| E1 多轮上下文记�?| �?| 2026-07-21 |
| �?thread 换题门闩（E1 补） | �?| 2026-07-23 |
| 条件精排（默�?RRF，歧义才 BGE�?| �?| 2026-07-23 |
| 条件多查询（默认单问，miss/超短才扩�?| �?| 2026-07-23 |
| Reranker 换模摸底（序 4 · Research �?· 缓做 I�?| �?Research · I �?| 2026-07-23 · [`tasks/retrieval-reranker-model-research.md`](tasks/retrieval-reranker-model-research.md) · 父链 [`tasks/retrieval-chain-conditional-research.md`](tasks/retrieval-chain-conditional-research.md) |
| E2 引用失效对话�?UX | �?| 2026-07-21 |
| E3 低置信度话术 | �?| 2026-07-21 |
| F1 引用硬对齐增�?| �?| 2026-07-21 |
| F2 跨库 citation 边界展示 | �?| 2026-07-21 |
| B1 异构 PDF 版式降噪 | �?| 2026-07-21 |
| B2 大表 / 跨页表格切分 | �?| 2026-07-21 |

## 当前基线�?026-08-14 完结口径�?

> SSOT：`backend/tests/benchmark/baseline.json`。检索门禁：Golden **11/11** 硬门禁（fixture �?GQ-9�? 全量 **109 �?135 passed**；Enterprise **60%**�?0 题非拒答，CI mock）�?真向�?**71.1%**�?/9 n=90）；Advanced **14/14**。CRAG / BeIR �?informational 外部基准�?

## 完结状�?

> **2026-08-14 完结收口**：待推进区已清零，默认队空、触发制停手；不再安排评�?/ 实验 / 功能开发。NW-23 等触发制暂停项保持冻结，不重新激活�?

> 地图 A～I �?· **NW-20�?6 �?* · **NW-47 Research ✅（I ⏸）** · **NW-48 Research ✅（I �?· 内网维持 24h�?* · **NW-49 �?* · **NW-50 �?* · **NW-51 �?*（审计政策永�?· �?purge I）�?**NW-52 �?*（安全姿态问�?· [`eval-ops-security-posture-questionnaire.md`](tasks/eval-ops-security-posture-questionnaire.md)）�?**NW-53 �?*（API �?root · [`nw53-api-nonroot-plan.md`](tasks/nw53-api-nonroot-plan.md)）�?**NW-54 �?*（检�?SLO · �?500 ms）�?**NW-55 �?*（对�?TTFT · [`nw55-chat-ttft-slo-plan.md`](tasks/nw55-chat-ttft-slo-plan.md) · �?000 ms）�?**NW-56 �?*（客户侧 TLS 薄配�?· [`eval-ops-client-tls-proxy-runbook.md`](tasks/eval-ops-client-tls-proxy-runbook.md)）�?**NW-57 �?*（web �?root · [`nw57-web-nonroot-plan.md`](tasks/nw57-web-nonroot-plan.md)）�?**NW-58 �?*（日历挂检�?SLO · [`nw58-maintenance-calendar-slo-plan.md`](tasks/nw58-maintenance-calendar-slo-plan.md)）�?**NW-59 Research ✅（I �?· Bearer+localStorage · [`nw59-httponly-csrf-research.md`](tasks/nw59-httponly-csrf-research.md)�?* · **NW-60 �?*（运维索引收�?· [`nw60-ops-index-post-nw59-plan.md`](tasks/nw60-ops-index-post-nw59-plan.md)）�?**NW-61 Research ✅（I �?· 预览 `?token=` · [`nw61-preview-query-token-research.md`](tasks/nw61-preview-query-token-research.md)�?* · **NW-62 �?*（日历挂对话 TTFT · [`nw62-maintenance-calendar-ttft-plan.md`](tasks/nw62-maintenance-calendar-ttft-plan.md) · 周检 W5 �?000 ms）�?**NW-63 Research ✅（I �?· CSP/安全�?· [`nw63-csp-security-headers-research.md`](tasks/nw63-csp-security-headers-research.md) · 默认维持 A�?* · **NW-64 �?*（BA/smoke 季回归挂�?· [`nw64-ba-smoke-quarterly-calendar-plan.md`](tasks/nw64-ba-smoke-quarterly-calendar-plan.md)）�?**NW-41 Research ✅（I ⏸）** · **NW-42 Research ✅（I ⏸）** · **post-nw34 �?* · **post-nw39 �?* · **post-nw44 �?* · **post-nw49 �?* · **post-nw54 �?* · **post-nw59 盘点 �?*（[`post-nw59-next-wave.md`](tasks/post-nw59-next-wave.md)�?*NW-60�?4 �?*）�?**post-nw64 盘点 �?*（[`post-nw64-next-wave.md`](tasks/post-nw64-next-wave.md)�?*NW-65�?9 �?* · **默认队空** · 继任 post-nw69）�?**post-nw69 盘点 �?*（[`post-nw69-next-wave.md`](tasks/post-nw69-next-wave.md)�?*NW-70�?4 �?* · **默认队空** · 继任 post-nw74）�?**post-nw74 盘点 �?*（[`post-nw74-next-wave.md`](tasks/post-nw74-next-wave.md)�?*NW-75 �?* · **默认队空 · 企业默认路径饱和 · 停手** · 内网交付验收 [`eval-ops-intranet-delivery-acceptance.md`](tasks/eval-ops-intranet-delivery-acceptance.md) · 首次 CVE 纪要 [`eval-ops-dependency-audit-2026-07-22.md`](tasks/eval-ops-dependency-audit-2026-07-22.md) · About/DEPLOY 指针 [`nw73-about-deploy-pointers-plan.md`](tasks/nw73-about-deploy-pointers-plan.md) · Plan [`nw75-ops-index-post-nw74-plan.md`](tasks/nw75-ops-index-post-nw74-plan.md)）�?**NW-23 �?* · **I-E / O3·O1 �?*；触发制�?post-nw74 §3（继�?post-nw69）；高敏感决�?[`eval-ops-high-sensitivity-posture.md`](tasks/eval-ops-high-sensitivity-posture.md)�?

| ID | 状�?| Plan |
|----|------|------|
| **NW-75** 运维索引收束�?post-nw74 | �?| [`nw75-ops-index-post-nw74-plan.md`](tasks/nw75-ops-index-post-nw74-plan.md) |
| **post-nw74** 再下一波盘�?| �?盘点 · §2 �?NW-75 �?· **默认队空 · 饱和停手** | [`post-nw74-next-wave.md`](tasks/post-nw74-next-wave.md) · 触发�?§3 |
| **NW-74** 内网交付验收一�?| �?| 验收 [`eval-ops-intranet-delivery-acceptance.md`](tasks/eval-ops-intranet-delivery-acceptance.md) · Plan [`nw74-intranet-delivery-acceptance-plan.md`](tasks/nw74-intranet-delivery-acceptance-plan.md) |
| **NW-73** About / DEPLOY 指针补齐 | �?| Plan [`nw73-about-deploy-pointers-plan.md`](tasks/nw73-about-deploy-pointers-plan.md) · 密钥轮换 · 高敏感表 · CVE 配方 |
| **NW-72** NW-66 首次实跑 audit 纪要 | �?· �?升版 I | 纪要 [`eval-ops-dependency-audit-2026-07-22.md`](tasks/eval-ops-dependency-audit-2026-07-22.md) · Plan [`nw72-dependency-audit-minutes-plan.md`](tasks/nw72-dependency-audit-minutes-plan.md) |
| **NW-71** 日历挂依�?镜像季干跑扫 | �?| [`nw71-maintenance-calendar-cve-plan.md`](tasks/nw71-maintenance-calendar-cve-plan.md) · 日历季检 Q6 |
| **NW-70** 运维索引收束�?post-nw69 | �?| [`nw70-ops-index-post-nw69-plan.md`](tasks/nw70-ops-index-post-nw69-plan.md) |
| **post-nw69** 再下一波盘�?| �?盘点 · §2 已确�?· **NW-70�?4 �?* · **默认队空** · 继任 post-nw74 | [`post-nw69-next-wave.md`](tasks/post-nw69-next-wave.md) · 触发�?§3 |
| **NW-69** 高敏感部署姿态决策表 | �?| Plan [`nw69-high-sensitivity-posture-plan.md`](tasks/nw69-high-sensitivity-posture-plan.md) · 决策�?[`eval-ops-high-sensitivity-posture.md`](tasks/eval-ops-high-sensitivity-posture.md) |
| **NW-68** 维护日历�?SA-1�? 季抽�?| �?| Plan [`nw68-sa-quarterly-calendar-plan.md`](tasks/nw68-sa-quarterly-calendar-plan.md) · 日历季检 Q5（与 BA Q4 分列�?|
| **NW-67** 密钥应急轮换一�?| �?| Plan [`nw67-secret-rotation-plan.md`](tasks/nw67-secret-rotation-plan.md) · 配方 [`eval-ops-secret-rotation-runbook.md`](tasks/eval-ops-secret-rotation-runbook.md) |
| **NW-66** 依赖/镜像 CVE 例行 Research | �?Research · 升版 I �?| Plan [`nw66-dependency-cve-research-plan.md`](tasks/nw66-dependency-cve-research-plan.md) · [`nw66-dependency-cve-research.md`](tasks/nw66-dependency-cve-research.md) |
| **NW-65** 运维索引收束�?post-nw64 | �?| [`nw65-ops-index-post-nw64-plan.md`](tasks/nw65-ops-index-post-nw64-plan.md) |
| **post-nw64** 再下一波盘�?| �?盘点 · §2 已确�?· **NW-65�?9 �?* · **默认队空** · 继任 post-nw69 | [`post-nw64-next-wave.md`](tasks/post-nw64-next-wave.md) · 触发�?§3 |
| **NW-64** BA / smoke 季回归挂维护日历 | �?| Plan [`nw64-ba-smoke-quarterly-calendar-plan.md`](tasks/nw64-ba-smoke-quarterly-calendar-plan.md) · 日历季检 Q4 抽验 |
| **NW-63** CSP / 安全响应�?Research | �?Research · **I �?* | Plan [`nw63-csp-security-headers-research-plan.md`](tasks/nw63-csp-security-headers-research-plan.md) · [`nw63-csp-security-headers-research.md`](tasks/nw63-csp-security-headers-research.md) · 默认维持 A · **�?Cookie I** |
| **NW-62** 维护日历挂对�?TTFT SLO | �?| Plan [`nw62-maintenance-calendar-ttft-plan.md`](tasks/nw62-maintenance-calendar-ttft-plan.md) · 周检 W5 �?000 ms（与检索分列） |
| **NW-61** 预览 `?token=` 收口 Research | �?Research · **I �?* | Plan [`nw61-preview-query-token-research-plan.md`](tasks/nw61-preview-query-token-research-plan.md) · [`nw61-preview-query-token-research.md`](tasks/nw61-preview-query-token-research.md) · 内网维持 A · **�?Cookie I / refresh I** |
| **NW-60** 运维索引收束�?post-nw59 | �?| [`nw60-ops-index-post-nw59-plan.md`](tasks/nw60-ops-index-post-nw59-plan.md) |
| **post-nw59** 再下一波盘�?| �?盘点 · **NW-60�?4 �?* · **默认队空** | [`post-nw59-next-wave.md`](tasks/post-nw59-next-wave.md) · 触发�?§3 |
| **NW-59** HttpOnly Cookie / CSRF Research | �?Research · **I �?* | Plan [`nw59-httponly-csrf-research-plan.md`](tasks/nw59-httponly-csrf-research-plan.md) · [`nw59-httponly-csrf-research.md`](tasks/nw59-httponly-csrf-research.md) · 内网维持 Bearer+localStorage · **�?refresh I** |
| **NW-58** 维护日历挂检�?SLO + 索引收束 | �?| Plan [`nw58-maintenance-calendar-slo-plan.md`](tasks/nw58-maintenance-calendar-slo-plan.md) · 周检 W4 �?500 ms |
| **NW-57** web 镜像�?root | �?| Plan [`nw57-web-nonroot-plan.md`](tasks/nw57-web-nonroot-plan.md) · nginx uid 101 · `80:8080` |
| **NW-56** 客户侧反�?TLS 薄配�?| �?| Plan [`nw56-client-tls-proxy-plan.md`](tasks/nw56-client-tls-proxy-plan.md) · 配方 [`eval-ops-client-tls-proxy-runbook.md`](tasks/eval-ops-client-tls-proxy-runbook.md) |
| **NW-55** 对话�?token / TTFT SLO 填数 | �?| Plan [`nw55-chat-ttft-slo-plan.md`](tasks/nw55-chat-ttft-slo-plan.md) · 纪要 [`eval-nw55-ttft-measure-2026-07-22.md`](tasks/eval-nw55-ttft-measure-2026-07-22.md) · �?000 ms |
| **post-nw54** 再下一波盘�?| �?盘点 · §2 NW-55�?*59 �?* · 继任 post-nw59 | [`post-nw54-next-wave.md`](tasks/post-nw54-next-wave.md) |
| **NW-54** 检�?对话延迟 SLO 填数 | �?| Plan [`nw54-retrieval-slo-measure-plan.md`](tasks/nw54-retrieval-slo-measure-plan.md) · 纪要 [`eval-nw54-slo-measure-2026-07-22.md`](tasks/eval-nw54-slo-measure-2026-07-22.md) |
| **NW-53** API 镜像�?root（SEC-7 �?I�?| �?| [`nw53-api-nonroot-plan.md`](tasks/nw53-api-nonroot-plan.md) |
| **NW-52** 企业安全姿态问卷一�?| �?| Plan [`nw52-security-posture-questionnaire-plan.md`](tasks/nw52-security-posture-questionnaire-plan.md) · 问卷 [`eval-ops-security-posture-questionnaire.md`](tasks/eval-ops-security-posture-questionnaire.md) |
| **NW-51** 审计政策永留文档（≠ purge I�?| �?| [`nw51-audit-policy-forever-plan.md`](tasks/nw51-audit-policy-forever-plan.md) |
| **NW-50** TECH SEC-7 / 内网 HTTP 口径 | �?| [`nw50-sec7-intranet-http-plan.md`](tasks/nw50-sec7-intranet-http-plan.md) |
| **post-nw49** 再下一波盘�?| �?盘点 · §2 NW-50�?*54 �?* · 默认队空 | [`post-nw49-next-wave.md`](tasks/post-nw49-next-wave.md) |
| **NW-49** 评测/发版维护日历 | �?| Plan [`nw49-eval-ops-maintenance-calendar-plan.md`](tasks/nw49-eval-ops-maintenance-calendar-plan.md) · 日历 [`eval-ops-maintenance-calendar.md`](tasks/eval-ops-maintenance-calendar.md) |
| **NW-48** refresh token / 登出吊销 Research | �?Research · **I �?* | [`nw48-refresh-token-revocation-research.md`](tasks/nw48-refresh-token-revocation-research.md) · 内网维持 24h · 触发制另开 plan |
| **NW-47** 审计日志保留�?Research | �?Research · **I �?* | [`nw47-audit-retention-research.md`](tasks/nw47-audit-retention-research.md) · 触发制另开 plan |
| **NW-46** 安全/运营开�?Admin 只读 | �?| [`nw46-ops-flags-readonly-plan.md`](tasks/nw46-ops-flags-readonly-plan.md) |
| **NW-45** 上传�?magic 双检 | �?| [`nw45-upload-magic-plan.md`](tasks/nw45-upload-magic-plan.md) |
| **post-nw44** 再下一波盘�?| �?盘点 · NW-45�?*49 �?* | [`post-nw44-next-wave.md`](tasks/post-nw44-next-wave.md) · §2 默认队空 · 触发制不进默认队 |
| **NW-44** 对话保留 Admin 只读可见 | �?| [`nw44-chat-retention-readonly-plan.md`](tasks/nw44-chat-retention-readonly-plan.md) |
| **NW-43** 运维索引防漂（About / DEPLOY / 值班�?| �?| [`nw43-ops-index-drift-plan.md`](tasks/nw43-ops-index-drift-plan.md) |
| **NW-42** ClamAV 上传扫毒 Research | �?Research · **I �?* | [`nw42-clamav-upload-scan-research.md`](tasks/nw42-clamav-upload-scan-research.md) · 触发制另开 A/B |
| **NW-41** SEC-8 删账号级�?Research | �?Research · **I �?* | [`nw41-account-deletion-cascade-research.md`](tasks/nw41-account-deletion-cascade-research.md) · 触发制另开 A |
| **NW-40** 库清单导出薄 UI | �?| [`nw40-kb-inventory-export-ui-plan.md`](tasks/nw40-kb-inventory-export-ui-plan.md) · 补完 NW-38 |
| **post-nw39** 再下一波盘�?| �?盘点 · 已确�?| [`post-nw39-next-wave.md`](tasks/post-nw39-next-wave.md) · NW-40�?4 · 触发制不进默认队 |
| **NW-39** Enterprise `observed_*` 尺子刷新 | �?| Plan [`nw39-observed-refresh-plan.md`](tasks/nw39-observed-refresh-plan.md) · 纪要 [`nw39-observed-refresh-2026-07-22.md`](tasks/nw39-observed-refresh-2026-07-22.md) |
| **NW-38** SEC-8 知识库清单导�?| �?| Research [`nw38-kb-inventory-export-research.md`](tasks/nw38-kb-inventory-export-research.md) · I [`nw38-kb-inventory-export-plan.md`](tasks/nw38-kb-inventory-export-plan.md) |
| **NW-37** 密码强度�?I | �?| [`nw37-password-strength-plan.md`](tasks/nw37-password-strength-plan.md) |
| **NW-36** M13 格式验收矩阵 | �?| [`nw36-m13-format-matrix-plan.md`](tasks/nw36-m13-format-matrix-plan.md) · 矩阵 [`eval-M13-format-matrix.md`](tasks/eval-M13-format-matrix.md) |
| **NW-35** 值班第四条（对话保留挂值班�?| �?| [`nw35-duty-chat-purge-plan.md`](tasks/nw35-duty-chat-purge-plan.md) · Runbook [`eval-ops-duty-triplet-runbook.md`](tasks/eval-ops-duty-triplet-runbook.md) |
| **post-nw34** 再下一波盘�?| �?盘点 | [`post-nw34-next-wave.md`](tasks/post-nw34-next-wave.md) · NW-35�?*39 �?* · 继任 [`post-nw39-next-wave.md`](tasks/post-nw39-next-wave.md) |
| **NW-20** 对话保留�?| �?I | Research [`nw20-chat-retention-research.md`](tasks/nw20-chat-retention-research.md) · I [`nw20-chat-retention-i-plan.md`](tasks/nw20-chat-retention-i-plan.md) |
| **NW-34** scrub �?LLM【检索片段�?| �?| Research [`nw34-llm-context-scrub-research.md`](tasks/nw34-llm-context-scrub-research.md) · I [`nw34-llm-context-scrub-plan.md`](tasks/nw34-llm-context-scrub-plan.md) |
| **NW-23** 真实 👎 二次审题 | �?**冻结** | 产品拍板先不做；解冻须再口头授权（≠ �?👎 即自动开�?|
| **NW-33** 「片段也不出境」私有化路径 | �?Research · **I-C �?*（S1）�?**I-E �?* | Research [`nw33-private-llm-path-research.md`](tasks/nw33-private-llm-path-research.md) · I-C [`nw33-ic-compat-endpoint-ops-plan.md`](tasks/nw33-ic-compat-endpoint-ops-plan.md) · 暂缓 [`nw33-ie-defer-2026-07-22.md`](tasks/nw33-ie-defer-2026-07-22.md) · NW-28 §12 |
| **NW-32** 审计日志 Admin 导出 CSV/JSON | �?| [`nw32-audit-export-plan.md`](tasks/nw32-audit-export-plan.md) |
| **NW-31** G3 只读 tool 白名单契�?pytest | �?| [`nw31-g3-tool-whitelist-contract-plan.md`](tasks/nw31-g3-tool-whitelist-contract-plan.md) |
| **NW-30** PRD/TECH 索引 4�? tool | �?| [`nw30-prd-tech-tool-index-plan.md`](tasks/nw30-prd-tech-tool-index-plan.md) |
| **post-nw29** 再下一波盘�?| �?盘点 | [`post-nw29-next-wave.md`](tasks/post-nw29-next-wave.md) · NW-33 Research �?· **NW-23 �?冻结** |
| **NW-29** R6-7 G3 只读 tool 契约设计 | �?设计 | [`nw29-r6-7-g3-tool-contract.md`](tasks/nw29-r6-7-g3-tool-contract.md) |
| **NW-28** 密钥�?LLM 出境运维薄页 | �?| Plan [`nw28-llm-egress-ops-plan.md`](tasks/nw28-llm-egress-ops-plan.md) · Runbook [`eval-ops-llm-egress-runbook.md`](tasks/eval-ops-llm-egress-runbook.md) |
| **NW-27** 引用 excerpt 脱敏规则（SEC-5�?| �?| [`nw27-citation-redaction-plan.md`](tasks/nw27-citation-redaction-plan.md) · Research [`nw27-citation-redaction-research.md`](tasks/nw27-citation-redaction-research.md) |
| **NW-26** 限流 429→`/metrics`（G2 N9�?| �?| [`nw26-rate-limit-metrics-plan.md`](tasks/nw26-rate-limit-metrics-plan.md) |
| **post-g2-n6** 再下一波盘�?| �?盘点 | [`post-g2-n6-next-wave.md`](tasks/post-g2-n6-next-wave.md) · NW-26�?9 �?· 继任 [`post-nw29-next-wave.md`](tasks/post-nw29-next-wave.md) |
| **G2 N6** 忘记密码限流 Redis | �?| [`g2-n6-forgot-password-rate-limit-plan.md`](tasks/g2-n6-forgot-password-rate-limit-plan.md) |
| **NW-25** 总库配额硬闸 + 用量 UI | �?I-1+I-2 | [`nw25-kb-quota-i2-plan.md`](tasks/nw25-kb-quota-i2-plan.md) |
| **NW-24** 部门 Admin 本节点成�?| �?I-1+I-2 | Research + [`nw24-unit-admin-members-i2-plan.md`](tasks/nw24-unit-admin-members-i2-plan.md) |
| **NW-22** H1→Grafana 告警薄配�?| �?| Plan [`nw22-h1-grafana-alert-plan.md`](tasks/nw22-h1-grafana-alert-plan.md) · Runbook [`eval-ops-h1-grafana-alert-runbook.md`](tasks/eval-ops-h1-grafana-alert-runbook.md) |
| **NW-21** API 限流 IP 接线（G2 N4�?| �?| [`nw21-api-rate-limit-ip-plan.md`](tasks/nw21-api-rate-limit-ip-plan.md) |
| **post-nw20** 再下一波盘�?| �?盘点 | [`post-nw20-next-wave.md`](tasks/post-nw20-next-wave.md) · 下一�?NW-23（有数据�? NW-24 |
| **NW-20** 对话保留�?Research | �?Research · **I �?* | Plan [`nw20-chat-retention-plan.md`](tasks/nw20-chat-retention-plan.md) · Research [`nw20-chat-retention-research.md`](tasks/nw20-chat-retention-research.md) · I [`nw20-chat-retention-i-plan.md`](tasks/nw20-chat-retention-i-plan.md) |
| **NW-19** M11 季检 + §3.4 改密 | �?| Plan [`nw19-m11-quarterly-check-plan.md`](tasks/nw19-m11-quarterly-check-plan.md) · 实跑 [`eval-M11-quarterly-check.md`](tasks/eval-M11-quarterly-check.md) |
| **NW-18** 首轮人工扩题 / 零采�?| �?| Plan [`nw18-first-manual-golden-expand-plan.md`](tasks/nw18-first-manual-golden-expand-plan.md) · 纪要 [`eval-nw18-zero-adoption-2026-07-22.md`](tasks/eval-nw18-zero-adoption-2026-07-22.md) |
| **NW-17** Admin 链审�?runbook | �?| Plan [`nw17-admin-thumbs-down-runbook-link-plan.md`](tasks/nw17-admin-thumbs-down-runbook-link-plan.md) · Runbook [`eval-thumbs-down-golden-runbook.md`](tasks/eval-thumbs-down-golden-runbook.md) |
| **NW-16** 值班三件套（orphan/purge/stale�?| �?· **NW-35 扩第四条** | Plan [`nw16-ops-duty-triplet-plan.md`](tasks/nw16-ops-duty-triplet-plan.md) · Runbook [`eval-ops-duty-triplet-runbook.md`](tasks/eval-ops-duty-triplet-runbook.md) · NW-35 [`nw35-duty-chat-purge-plan.md`](tasks/nw35-duty-chat-purge-plan.md) |
| **NW-11** M11-B1 库密 + §3 浏览�?| �?| [`nw11-m11-b1-b9-plan.md`](tasks/nw11-m11-b1-b9-plan.md) · checklist [`eval-M11-release-checklist.md`](tasks/eval-M11-release-checklist.md) |
| **NW-12** Celery stale 自愈 | �?| [`nw12-celery-stale-backlog-plan.md`](tasks/nw12-celery-stale-backlog-plan.md) |
| **NW-13** 找文�?+ 库内正文 | �?| [`nw13-in-kb-search-r2-plan.md`](tasks/nw13-in-kb-search-r2-plan.md) |
| **NW-14** 👎→golden 人工审题 | �?| [`nw14-thumbs-down-golden-plan.md`](tasks/nw14-thumbs-down-golden-plan.md) · Runbook [`eval-thumbs-down-golden-runbook.md`](tasks/eval-thumbs-down-golden-runbook.md) |
| **NW-15** H4 成对 restore | �?| Plan [`nw15-paired-restore-plan.md`](tasks/nw15-paired-restore-plan.md) · 演练 [`eval-M10-backup-drill-2026-07-22.md`](tasks/eval-M10-backup-drill-2026-07-22.md) · M11 §4.6 �?|
| **NW-6** M11 发版日补�?+ B3 积压 + B7 | �?| [`nw6-m11-release-day-plan.md`](tasks/nw6-m11-release-day-plan.md) · [`eval-M11-release-checklist.md`](tasks/eval-M11-release-checklist.md) |
| **NW-7** 文档断链 + PRD/索引漂移 | �?| [`nw7-doc-prd-drift-plan.md`](tasks/nw7-doc-prd-drift-plan.md) · [`post-nw-next-wave.md`](tasks/post-nw-next-wave.md) |
| **NW-8** embed readiness（M11-B8�?| �?| [`nw8-embed-readiness-plan.md`](tasks/nw8-embed-readiness-plan.md) |
| **NW-9** 通义 chat 可切�?| �?| [`nw9-chat-provider-plan.md`](tasks/nw9-chat-provider-plan.md) |
| **NW-10** R6-4 反馈 I-1·I-2·I-3 | �?| Research [`nw10-feedback-r6-4-research.md`](tasks/nw10-feedback-r6-4-research.md) · Plan [`nw10-feedback-r6-4-plan.md`](tasks/nw10-feedback-r6-4-plan.md) |
| 地图结案后第一�?NW-1�? | �?| [`post-map-next-wave.md`](tasks/post-map-next-wave.md) |
| **B1** 异构 PDF 版式降噪 | �?| [`p0b-b1-pdf-layout-denoise-plan.md`](tasks/p0b-b1-pdf-layout-denoise-plan.md) |
| **B2** 大表 / 跨页表格 | �?| [`p0b-b2-table-chunk-plan.md`](tasks/p0b-b2-table-chunk-plan.md) |
| B3 OCR 失败可观�?| �?Implement | [`p0b-b3-ocr-observability-plan.md`](tasks/p0b-b3-ocr-observability-plan.md) |
| B4 中英双嵌�?| �?Implement | [`p0b-b4-dual-embedding-plan.md`](tasks/p0b-b4-dual-embedding-plan.md) · Research [`p0b-b4-dual-embedding-research.md`](tasks/p0b-b4-dual-embedding-research.md) |
| **H1** Prometheus 核心指标 | �?| Plan [`p2h-h1-prometheus-metrics-plan.md`](tasks/p2h-h1-prometheus-metrics-plan.md) · Research [`p2h-h1-prometheus-metrics-research.md`](tasks/p2h-h1-prometheus-metrics-research.md) |
| **H2** orphan 定时扫描 | �?| Plan [`p2h-h2-orphan-scan-plan.md`](tasks/p2h-h2-orphan-scan-plan.md) · Research [`p2h-h2-orphan-scan-research.md`](tasks/p2h-h2-orphan-scan-research.md) |
| **H3** 软删 / 回收�?| �?| Plan [`p2h-h3-soft-delete-trash-plan.md`](tasks/p2h-h3-soft-delete-trash-plan.md) · Research [`p2h-h3-soft-delete-trash-research.md`](tasks/p2h-h3-soft-delete-trash-research.md) |
| **H4** 备份演练 + SLO 文档 | �?| Plan [`p2h-h4-backup-slo-plan.md`](tasks/p2h-h4-backup-slo-plan.md) · Research [`p2h-h4-backup-slo-research.md`](tasks/p2h-h4-backup-slo-research.md) · Runbook [`eval-M10-backup-runbook.md`](tasks/eval-M10-backup-runbook.md) |
| **G1** Celery 生产默认（非 eager�?| �?| Plan [`p2g-g1-celery-prod-default-plan.md`](tasks/p2g-g1-celery-prod-default-plan.md) · Research [`p2g-g1-celery-prod-default-research.md`](tasks/p2g-g1-celery-prod-default-research.md) |
| **G2** Redis 跨副本限�?| �?| Plan [`p2g-g2-redis-rate-limit-plan.md`](tasks/p2g-g2-redis-rate-limit-plan.md) · Research [`p2g-g2-redis-rate-limit-research.md`](tasks/p2g-g2-redis-rate-limit-research.md) |
| **I1** 跨库结果分页 | �?| Plan [`p2i-i1-cross-kb-search-pagination-plan.md`](tasks/p2i-i1-cross-kb-search-pagination-plan.md) · Research [`p2i-i1-cross-kb-search-pagination-research.md`](tasks/p2i-i1-cross-kb-search-pagination-research.md) |
| **I2** 跨库搜索�?延迟 | �?测量优先 | Plan [`p2i-i2-search-index-latency-plan.md`](tasks/p2i-i2-search-index-latency-plan.md) · Research [`p2i-i2-search-index-latency-research.md`](tasks/p2i-i2-search-index-latency-research.md) · 报告 [`eval-M2-search-report.md`](tasks/eval-M2-search-report.md)；O3/O1 backlog |

## 已关闭不做的

| 原计�?| 原因 |
|--------|------|
| RAGAS 接入 | RAGAS 双轨 judge 已作为观测口径（2026-08-14 冻结），不进�?CI 门禁 |
| HTTPS 部署 | 内网 HTTP，无公网需�?|
| 支付/积分 | 不在企业�?roadmap |
