import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { VitalCard } from "@/components/dashboard/VitalCard";
import { IngestionPanel } from "@/components/dashboard/IngestionPanel";
import { RagProofCard } from "@/components/dashboard/RagProofCard";
import { PerfTable } from "@/components/dashboard/PerfTable";
import { ActivityChart } from "@/components/dashboard/ActivityChart";
import { CompositionBar } from "@/components/dashboard/CompositionBar";
import { FeedList } from "@/components/dashboard/FeedList";
import { EmptyStateV44, DASHBOARD_SCENE } from "@/components/ui/EmptyState";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { Toast, useToast } from "@/components/ui/Toast";
import {
  fetchDashboardStats,
  isDashboardEmpty,
  type DashboardStats,
} from "@/lib/dashboard-api";
import {
  formatK,
  mapActivitiesToFeed,
  mapThreadsToFeed,
} from "@/lib/dashboard-format";
import {} from "@/lib/org-permissions";
import { useDepartment } from "@/lib/department-context";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";
import { useWorkspace } from "@/lib/workspace-context";
import { useAuth } from "@/lib/auth-context";
import { SectionTitle } from "@/components/common/SectionTitle";

export function DashboardPage() {
  const navigate = useNavigate();
  const {} = useAuth();
  const { workspace, generation, getGeneration } = useWorkspace();
  const {
    departmentId,
    generation: deptGen,
    getGeneration: getDeptGen,
  } = useDepartment();
  const { toast, dismiss: dismissToast } = useToast();
  const { setOverride } = useShellBreadcrumb();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [footOpen, setFootOpen] = useState(false);

  const loadStats = useCallback(async () => {
    const eg = generation;
    const ed = deptGen;
    setLoading(true); setError(null); setStats(null);
    try {
      const data = await fetchDashboardStats({
        expectedGen: eg, getCurrentGeneration: getGeneration,
        expectedDepartmentGen: ed, getCurrentDepartmentGeneration: getDeptGen,
        workspace,
        departmentId: workspace === "personal" ? null : departmentId,
      });
      if (data === null || getGeneration() !== eg || getDeptGen() !== ed) return;
      setStats(data);
    } catch (err) {
      if (getGeneration() !== eg || getDeptGen() !== ed) return;
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      if (getGeneration() === eg && getDeptGen() === ed) setLoading(false);
    }
  }, [workspace, generation, getGeneration, departmentId, deptGen, getDeptGen]);

  useEffect(() => { void loadStats(); }, [loadStats]);
  useEffect(() => { setOverride(null); document.title = "睿阁 · 概览"; }, [setOverride]);

  const isEmpty = stats !== null && isDashboardEmpty(stats);

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-[1180px] p-7">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-[110px] animate-pulse rounded-2xl border border-[var(--line2)] bg-[var(--surf)]" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-[1180px] p-7">
        <AlertBanner action={<Button type="button" variant="outline" size="sm" onClick={loadStats}>重试</Button>}>
          {error}
        </AlertBanner>
      </div>
    );
  }

  if (!stats || isEmpty) {
    return (
      <div className="mx-auto max-w-[1180px] p-7">
        <EmptyStateV44 scene={{ ...DASHBOARD_SCENE, ctaPrimary: { ...DASHBOARD_SCENE.ctaPrimary, onClick: () => navigate("/knowledge-bases") }, ctaSecondary: { ...DASHBOARD_SCENE.ctaSecondary, onClick: () => navigate("/knowledge-bases") } }} />
      </div>
    );
  }

  /* ── 有数据：渲染驾驶舱 ── */
  const ds = stats.documents_by_status;
  const actFeed = mapActivitiesToFeed(stats.recent_activities);

  return (
    <div className="mx-auto w-full max-w-[1180px] px-7 pb-16 pt-7">
      {/* KPI Ribbon — 关键指标（grid 确保等宽，避免 flex 项计算不一致） */}
      <section aria-label="关键指标">
        {isEmpty ? (
          <div className="mb-7 flex flex-col items-center gap-3 rounded-2xl border border-dashed border-[var(--line2)] bg-[var(--surf)] py-10 text-center">
            <p className="font-[var(--serif)] text-[18px] font-semibold text-[var(--text)]">
              开始用睿阁
            </p>
            <p className="max-w-[420px] text-sm leading-[1.6] text-[var(--mut-warm)]">
              新建一个资料库并上传文档，AI 即可在对话中带引用回答；先去对话看看示例也行。
            </p>
            <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="brand"
                onClick={() => navigate("/knowledge-bases")}
              >
                去新建资料库
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => navigate("/ask")}
              >
                去对话看看
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-7">
            <VitalCard value={stats.knowledge_base_count} label="资料库" hint="scope 可见" href="/knowledge-bases" />
            <VitalCard value={stats.document_count} label="已入库文件" hint={`可提问 ${ds.completed}`} accent="ok" href={stats.recent_kb_id ? `/knowledge-bases/${stats.recent_kb_id}` : "/knowledge-bases"} />
            <VitalCard value={stats.chat_message_count} label="近 7 日提问" hint="含引用溯源" accent="info" href="/ask" />
            {stats.member_count !== null && (
              <VitalCard value={stats.member_count} label="团队成员" hint="企业版" />
            )}
          </div>
        )}
      </section>

      {/* 入库态势 — 文档流转与存储健康 */}
      <section aria-label="入库态势">
        <SectionTitle label="入库态势" en="Ingestion Pipeline" />
        <IngestionPanel
          docStatus={ds}
          successRate={stats.ingestion_success_rate}
          avgDuration={stats.avg_processing_duration_seconds}
          chunkCount={stats.total_chunk_count}
          retryCount7d={stats.document_retry_count_7d}
          cleanFailureCount={stats.storage_cleanup_failure_count}
          recentKbName={stats.recent_kb_name}
        />
      </section>

      {/* 可信与性能 — RAG 可证明性 */}
      <section aria-label="可信与性能">
        <SectionTitle label="可信与性能" en="RAG Proof & Latency" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="h-full">
          <RagProofCard hitRate={stats.golden_hit_rate_percent} evaluatedAt={stats.golden_baseline_evaluated_at} note={stats.golden_hit_rate_percent !== null ? `${stats.golden_hit_rate_percent}% 基线 — 引用溯源可信` : undefined} />
          </div>
          <div className="h-full">
          <PerfTable latency={stats.avg_retrieval_latency_ms} sampleCount={stats.retrieval_latency_sample_count} />
          </div>
        </div>
      </section>

      {/* 活跃度 — 提问趋势与知识构成 */}
      <section aria-label="活跃度">
        <SectionTitle label="活跃度" en="Activity" />
        <div className="grid grid-cols-1 md:grid-cols-[1.4fr_1fr] gap-4">
          {/* 趋势图：近 7 日按日分桶提问数（真实聚合） */}
          <ActivityChart
            points={stats.question_trend}
            onDayClick={(date) => navigate(`/ask?date=${date}`)}
          />
          <CompositionBar
            items={stats.format_distribution.map((f) => ({
              name: f.format,
              count: f.count,
              percent: stats.document_count > 0 ? Math.round((f.count / stats.document_count) * 100) : 0,
            }))}
            totalLabel="文档总数"
            totalValue={String(stats.document_count)}
            chunkCount={formatK(stats.total_chunk_count)}
          />
        </div>
      </section>

      {/* 最近对话与动态 */}
      <section aria-label="最近对话与动态">
        <SectionTitle label="最近对话与动态" en="Threads & Audit" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FeedList title="最近对话" tag="/ask-threads" items={mapThreadsToFeed(stats.recent_threads).length > 0 ? mapThreadsToFeed(stats.recent_threads) : []} emptyText="暂无对话记录" />
          <FeedList title="操作动态" tag="audit" items={actFeed.length > 0 ? actFeed.slice(0, 5) : []} emptyText="暂无操作动态" emptyIcon="refresh-cw" />
        </div>
      </section>

      {/* Footer 数据口径（平滑展开/收起动画） */}
      <footer className="mt-[34px] border-t border-[var(--line2)] pt-4">
        <button
          type="button"
          onClick={() => setFootOpen(!footOpen)}
          className={`border-0 bg-transparent text-xs text-[var(--mut)] cursor-pointer inline-flex items-center gap-[5px] py-[6px] hover:text-[var(--text)] transition-colors font-sans ${
            footOpen ? "open" : ""
          }`}
          aria-expanded={footOpen}
          aria-controls="footDetail"
        >
          数据口径{" "}
          <span
            className={`text-[9px] transition-transform duration-200 ${footOpen ? "rotate-180" : ""}`}
            style={{ display: "inline-block" }}
          >
            ▾
          </span>
        </button>
        <div
          id="footDetail"
          className="overflow-hidden transition-all duration-300 ease-in-out"
          style={{
            maxHeight: footOpen ? "400px" : "0",
            opacity: footOpen ? 1 : 0,
            marginTop: footOpen ? "12px" : 0,
          }}
        >
          <div className="text-xs leading-relaxed text-[var(--mut)]">
            主轴数据来自后端{" "}
            <span className="font-semibold">GET /api/v1/dashboard/stats</span>{" "}
            实时聚合，按 workspace / kb 可见集隔离。核心字段包括：
            knowledge_base_count、documents_by_status（queued / processing / completed / failed）、
            ingestion_success_rate、total_chunk_count、chat_message_count、
            golden_hit_rate_percent、avg_retrieval_latency_ms、retrieval_latency_sample_count。
            <br /><br />
            趋势图按近 7 日按日分桶（question_trend）；知识构成按文档格式聚合（format_distribution）；
            最近对话来自 recent_threads（含 citation_count）；操作动态来自 recent_activities（type 映射图标）。
            标注「待聚合 / 待接入」的项需小幅后端支撑：① Document.file_type/file_size 聚合（知识构成体积）
            ② ChatMessage.citations 覆盖率（引用覆盖率）③ 操作审计聚合粒度。
            属 Tier-1 的主轴数据无需改后端即可上线。
          </div>
        </div>
      </footer>

      <Toast message={toast?.message ?? null} onDismiss={dismissToast} />
    </div>
  );
}
