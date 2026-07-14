import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { VitalCard } from "@/components/dashboard/VitalCard";
import { IngestionPanel } from "@/components/dashboard/IngestionPanel";
import { RagProofCard } from "@/components/dashboard/RagProofCard";
import { PerfTable } from "@/components/dashboard/PerfTable";
import { TrendChart } from "@/components/dashboard/TrendChart";
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
  formatTrendLabels,
  mapActivitiesToFeed,
  mapThreadsToFeed,
} from "@/lib/dashboard-format";
import {} from "@/lib/org-permissions";
import { useDepartment } from "@/lib/department-context";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";
import { useWorkspace } from "@/lib/workspace-context";
import { useAuth } from "@/lib/auth-context";

/* ── 章节标题 ── */
function SectionTitle({ label, en }: { label: string; en?: string }) {
  return (
    <div className="flex items-baseline gap-2.5 my-8 mb-3.5">
      <span className="relative pl-3.5 font-[var(--serif)] text-[17px] font-semibold">
        {label}
        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-[15px] w-[4px] rounded-[2px] bg-[var(--brand)]" />
      </span>
      {en && (
        <span className="text-[11px] tracking-widest uppercase text-[var(--mut)]">{en}</span>
      )}
      <span className="flex-1 h-px bg-[var(--line2)]" />
    </div>
  );
}

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
      {/* KPI Ribbon */}
      <div className="flex flex-wrap gap-3 mb-7">
        <VitalCard value={stats.knowledge_base_count} label="资料库" hint="scope 可见" href="/knowledge-bases" />
        <VitalCard value={stats.document_count} label="已入库文件" hint={`可提问 ${ds.completed}`} accent="ok" href={stats.recent_kb_id ? `/knowledge-bases/${stats.recent_kb_id}` : "/knowledge-bases"} />
        <VitalCard value={stats.chat_message_count} label="近 7 日提问" hint="含引用溯源" accent="info" href="/ask" />
        {stats.member_count !== null && (
          <VitalCard value={stats.member_count} label="团队成员" hint="企业版" />
        )}
      </div>

      {/* 入库态势 */}
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

      {/* 可信与性能 */}
      <SectionTitle label="可信与性能" en="RAG Proof & Latency" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <RagProofCard hitRate={stats.golden_hit_rate_percent} evaluatedAt={stats.golden_baseline_evaluated_at} note={stats.golden_hit_rate_percent !== null ? `${stats.golden_hit_rate_percent}% 基线 — 引用溯源可信` : undefined} />
        <PerfTable latency={stats.avg_retrieval_latency_ms} sampleCount={stats.retrieval_latency_sample_count} />
      </div>

      {/* 活跃度 */}
      <SectionTitle label="活跃度" en="Activity" />
      <div className="grid grid-cols-1 md:grid-cols-[1.4fr_1fr] gap-4">
        {/* 趋势图：近 7 日按日分桶提问数（真实聚合） */}
        <TrendChart data={stats.question_trend.map((t) => t.count)} labels={formatTrendLabels(stats.question_trend)} />
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

      {/* 最近对话与动态 */}
      <SectionTitle label="最近对话与动态" en="Threads & Audit" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FeedList title="最近对话" tag="/ask-threads" items={mapThreadsToFeed(stats.recent_threads).length > 0 ? mapThreadsToFeed(stats.recent_threads) : [{ iconName: "message-square", title: "暂无对话", meta: "发起提问后显示" }]} />
        <FeedList title="操作动态" tag="audit" items={actFeed.length > 0 ? actFeed.slice(0, 5) : [{ iconName: "refresh-cw", title: "暂无操作记录", meta: "操作审计聚合待接入" }]} />
      </div>

      {/* Footer 数据口径 */}
      <div className="mt-10 border-t border-[var(--line2)] pt-4">
        <button type="button" onClick={() => setFootOpen(!footOpen)} className="border-0 bg-transparent text-[11px] text-[var(--mut)] cursor-pointer inline-flex items-center gap-1.5 hover:text-[var(--text)] transition-colors font-sans tracking-wide">
          数据口径 <span className={`text-[9px] transition-transform ${footOpen ? "rotate-180" : ""}`}>▾</span>
        </button>
        {footOpen && (
          <div className="mt-3 text-[11px] leading-relaxed text-[var(--mut)]">
            主轴数据来自后端 <span className="font-semibold">GET /dashboard/stats</span> 实时聚合（knowledge_base_count、documents_by_status、ingestion_success_rate、total_chunk_count、chat_message_count、golden_hit_rate_percent 等）。
            趋势、格式分布、最近对话与操作动态均为后端按 workspace / kb 可见集隔离的实时聚合。
          </div>
        )}
      </div>

      <Toast message={toast?.message ?? null} onDismiss={dismissToast} />
    </div>
  );
}
