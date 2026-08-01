import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  fetchDashboardStats,
  type DashboardStats,
} from "@/lib/dashboard-api";
import { fetchFeedbackStats, type FeedbackStats } from "@/lib/feedback-api";
import { useDepartment } from "@/lib/department-context";
import { useWorkspace } from "@/lib/workspace-context";

/** 团队 Admin 运维入口：文档路径 + M4 成本粗估 + NW-10 反馈聚合 + NW-16/35 值班 + NW-17 审题 + NW-22 H1 告警 + NW-28 密钥/出境 + NW-36 M13 + NW-40 资产清单 + NW-43 季检指针 + NW-44 对话保留只读 + NW-46 安全/运营开关只读 + NW-49 维护日历 + NW-51 审计永留只读 + NW-52 安全姿态问卷 + NW-73 密钥轮换/高敏感表/CVE 配方 + NW-74 内网交付验收 + Enterprise 尺子（观测 vs 冻结）。 */

function formatKbQuota(bytes: number): string {
  if (bytes === 0) return "关闭（KB_QUOTA_MAX_BYTES=0）";
  const gib = bytes / 1024 ** 3;
  if (Number.isInteger(gib) || Math.abs(gib - Math.round(gib)) < 1e-9) {
    return `开（${Math.round(gib)} GiB）`;
  }
  return `开（${bytes.toLocaleString()} 字节）`;
}

function onOff(enabled: boolean): string {
  return enabled ? "开" : "关";
}

export function AboutOpsSection() {
  const { workspace, generation, getGeneration } = useWorkspace();
  const {
    departmentId,
    generation: deptGen,
    getGeneration: getDeptGen,
  } = useDepartment();
  const [opsStats, setOpsStats] = useState<DashboardStats | null>(null);
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(
    null,
  );

  const loadOpsStats = useCallback(async () => {
    const eg = generation;
    const ed = deptGen;
    try {
      const data = await fetchDashboardStats({
        expectedGen: eg,
        getCurrentGeneration: getGeneration,
        expectedDepartmentGen: ed,
        getCurrentDepartmentGeneration: getDeptGen,
        workspace,
        departmentId: workspace === "personal" ? null : departmentId,
      });
      if (data === null || getGeneration() !== eg || getDeptGen() !== ed) return;
      setOpsStats(data);
    } catch {
      if (getGeneration() !== eg || getDeptGen() !== ed) return;
      setOpsStats(null);
    }
  }, [generation, deptGen, getGeneration, getDeptGen, workspace, departmentId]);

  const loadFeedbackStats = useCallback(async () => {
    try {
      const data = await fetchFeedbackStats();
      setFeedbackStats(data);
    } catch {
      setFeedbackStats(null);
    }
  }, []);

  useEffect(() => {
    void loadOpsStats();
  }, [loadOpsStats]);

  useEffect(() => {
    void loadFeedbackStats();
  }, [loadFeedbackStats]);

  return (
    <section aria-label="运维入口" data-testid="about-ops">
      <h2 className="mb-3 font-[var(--serif)] text-[17px] font-semibold text-[var(--text)]">
        运维入口
      </h2>
      <p className="mb-3 text-sm text-[var(--mut)]">
        仅组织管理员可见。仓库文档不由本页托管，请在部署机打开下列路径。
      </p>
      <ul className="space-y-2 text-sm text-[var(--mut)]">
        <li>
          <Link
            to="/admin/audit"
            className="text-[var(--action)] hover:underline"
          >
            操作审计日志
          </Link>
        </li>
        <li>
          <Link
            to="/admin/kb-inventory"
            className="text-[var(--action)] hover:underline"
          >
            知识库资产清单
          </Link>
          <span className="text-[var(--mut)]">
            （文档 metadata，≠ 审计导出）
          </span>
        </li>
        <li>
          部署清单：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/DEPLOY.md
          </code>
        </li>
        <li>
          备份 runbook：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-M10-backup-runbook.md
          </code>
        </li>
        <li>
          值班四件套（orphan / trash / stale / 对话保留 · 干跑）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-ops-duty-triplet-runbook.md
          </code>
        </li>
        <li>
          格式验收矩阵（M13 · 人工勾选）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-M13-format-matrix.md
          </code>
        </li>
        <li>
          H1 指标告警配方（拒答 / 积压 / 延迟）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-ops-h1-grafana-alert-runbook.md
          </code>
        </li>
        <li>
          密钥与 LLM 出境说明：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-ops-llm-egress-runbook.md
          </code>
        </li>
        <li>
          密钥应急轮换（JWT / API Key）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-ops-secret-rotation-runbook.md
          </code>
        </li>
        <li>
          高敏感部署姿态决策表：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-ops-high-sensitivity-posture.md
          </code>
        </li>
        <li>
          依赖/镜像 CVE 例行配方：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/nw66-dependency-cve-research.md
          </code>
        </li>
        <li>
          成本 / 用量粗算（非计费）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-M4-cost-model.md
          </code>
        </li>
        <li>
          👎→golden 人工审题：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-thumbs-down-golden-runbook.md
          </code>
        </li>
        <li>
          M11 季检最小集（维护）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-M11-quarterly-check.md
          </code>
        </li>
        <li>
          评测/发版维护日历（日/周/季）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-ops-maintenance-calendar.md
          </code>
        </li>
        <li>
          Enterprise 尺子（现网观测 ≠ 门禁冻结）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/nw2b-ruler-alignment.md
          </code>
        </li>
        <li>
          企业安全姿态问卷（可抄）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-ops-security-posture-questionnaire.md
          </code>
        </li>
        <li>
          内网交付验收一页（可勾）：
          <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            docs/tasks/eval-ops-intranet-delivery-acceptance.md
          </code>
        </li>
      </ul>
      <p
        className="mt-3 text-sm text-[var(--mut)]"
        data-testid="about-ops-boundary"
      >
        边界：密钥轮换 / 高敏感表 / CVE
        配方仅为运维文档入口；≠ 开 Cookie I · ≠
        产品已私有化 · ≠ 已升版依赖。不做设置页。
      </p>
      <p
        className="mt-4 text-sm text-[var(--mut)]"
        data-testid="about-audit-retention"
      >
        审计：
        <span className="text-[var(--text)]">永留（无 TTL）</span>
        。默认不按龄删；靠 PG 备份轮转。与下方「对话保留」独立；无 purge CLI。
      </p>
      {opsStats != null && opsStats.chat_retention_days != null ? (
        <p
          className="mt-2 text-sm text-[var(--mut)]"
          data-testid="about-chat-retention"
        >
          对话保留：
          <span className="tabular-nums text-[var(--text)]">
            {opsStats.chat_retention_days === 0
              ? "关闭（CHAT_RETENTION_DAYS=0）"
              : `${opsStats.chat_retention_days} 天`}
          </span>
          。只读；改 TTL 须改环境变量后重启。值班第四条见上方「值班四件套」路径（干跑默认，不上 Beat）。≠ 审计永留。
        </p>
      ) : null}
      {opsStats != null && opsStats.rate_limit_backend != null ? (
        <div
          className="mt-4 space-y-1.5 text-sm text-[var(--mut)]"
          data-testid="about-ops-flags"
        >
          <p>
            限流后端：
            <span className="tabular-nums text-[var(--text)]">
              {opsStats.rate_limit_backend}
            </span>
            （RATE_LIMIT_BACKEND）。
          </p>
          <p>
            引用脱敏：
            <span className="text-[var(--text)]">
              {onOff(Boolean(opsStats.citation_redact_enabled))}
            </span>
            （CITATION_REDACT_ENABLED）。
          </p>
          <p>
            送模 scrub：
            <span className="text-[var(--text)]">
              {onOff(Boolean(opsStats.llm_context_redact_enabled))}
            </span>
            （LLM_CONTEXT_REDACT_ENABLED）。
          </p>
          <p>
            总库配额：
            <span className="tabular-nums text-[var(--text)]">
              {formatKbQuota(opsStats.kb_quota_max_bytes ?? 0)}
            </span>
            。
          </p>
          <p>只读；改开关须改环境变量后重启。不做设置页。</p>
        </div>
      ) : null}
      {opsStats != null && opsStats.estimated_api_cost_cny_7d != null ? (
        <p
          className="mt-2 text-sm text-[var(--mut)]"
          data-testid="about-cost-estimate"
        >
          近 7 日可见范围：提问{" "}
          <span className="tabular-nums text-[var(--text)]">
            {opsStats.usage_7d_user_questions}
          </span>
          、助手回复{" "}
          <span className="tabular-nums text-[var(--text)]">
            {opsStats.usage_7d_assistant_replies}
          </span>
          ；对话 API 粗估约{" "}
          <span className="tabular-nums text-[var(--text)]">
            ¥{opsStats.estimated_api_cost_cny_7d.toFixed(2)}
          </span>
          （非账单，详见成本说明）。
        </p>
      ) : null}
      {feedbackStats != null ? (
        <p
          className="mt-2 text-sm text-[var(--mut)]"
          data-testid="about-feedback-stats"
        >
          对话反馈（组织聚合，非计费）：共{" "}
          <span className="tabular-nums text-[var(--text)]">
            {feedbackStats.total}
          </span>
          条 · 有帮助{" "}
          <span className="tabular-nums text-[var(--text)]">
            {feedbackStats.thumbs_up}
          </span>
          · 没帮助{" "}
          <span className="tabular-nums text-[var(--text)]">
            {feedbackStats.thumbs_down}
          </span>
          {feedbackStats.total > 0 ? (
            <>
              （认可率{" "}
              <span className="tabular-nums text-[var(--text)]">
                {(feedbackStats.approval_rate * 100).toFixed(0)}%
              </span>
              ）
            </>
          ) : null}
          。只记元数据，不自动改检索。
        </p>
      ) : null}
      <div
        className="mt-3 space-y-1.5 text-sm text-[var(--mut)]"
        data-testid="about-thumbs-down-export-hint"
      >
        <p>导出 👎 候选（在 backend/，连目标库；导出 ≠ 进门禁）：</p>
        <p>
          <code className="block break-all rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            python scripts/export_thumbs_down_candidates.py
          </code>
        </p>
        <p>
          <code className="block break-all rounded bg-[var(--surf2)] px-1.5 py-0.5 text-[var(--text)]">
            {"python scripts/export_thumbs_down_candidates.py --out ..\\tmp\\thumbs_down_candidates.json"}
          </code>
        </p>
        <p>
          须人工对照源文档后再手工改 fixture。不一键写入、不自动改检索。
        </p>
      </div>
    </section>
  );
}
