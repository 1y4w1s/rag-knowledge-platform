import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { VitalCard } from "@/components/dashboard/VitalCard";
import { IngestionPanel } from "@/components/dashboard/IngestionPanel";
import { RagProofCard } from "@/components/dashboard/RagProofCard";
import { PerfTable } from "@/components/dashboard/PerfTable";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { CompositionBar } from "@/components/dashboard/CompositionBar";
import { FeedList, type FeedItem } from "@/components/dashboard/FeedList";
import { EmptyStateV44, DASHBOARD_SCENE } from "@/components/ui/EmptyState";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { Toast, useToast } from "@/components/ui/Toast";
import {
  fetchDashboardStats,
  isDashboardEmpty,
  type DashboardStats,
} from "@/lib/dashboard-api";
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

/* ── 将 recent_activities 映射为 FeedItem ── */
function mapActivitiesToFeed(activities: DashboardStats["recent_activities"]): FeedItem[] {
  return activities.map((a) => ({
    iconName: "upload",
    title: `操作: ${a.title}`,
    meta: a.kb_id ? `kb:${a.kb_id.slice(0, 8)}` : "全局",
    time: a.created_at
      ? new Date(a.created_at).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })
      : undefined,
  }));
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
        workspace: workspace === "personal" ? "personal" : "organization",
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
        recentKbName={stats.recent_kb_id ? "产品手册" : null} // TODO: 接入 kb name API
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
        {/* 趋势图：暂无按日分桶数据，显示占位或隐藏 */}
        <TrendChart data={[9,14,11,18,22,31,32]} labels={["7天前","","4天前","","今天"]} />
        <CompositionBar items={[{name:"PDF",count:129,percent:52},{name:"DOCX",count:69,percent:28},{name:"TXT",count:30,percent:12},{name:"其他",count:20,percent:8}]} totalValue="1.8GB" chunkCount="18.4k" />
      </div>

      {/* 最近对话与动态 */}
      <SectionTitle label="最近对话与动态" en="Threads & Audit" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <FeedList title="最近对话" tag="/ask-threads" items={[
          { iconName: "message-square", title: "如何配置 RBAC 角色？", meta: "3 条引用 · 2小时前" },
          { iconName: "message-square", title: "嵌入模型选型对比", meta: "5 条引用 · 昨天" },
          { iconName: "message-square", title: "PDF 表格解析失败原因", meta: "2 条引用 · 昨天" },
        ]} />
        <FeedList title="操作动态" tag="audit · 待接入" items={actFeed.length > 0 ? actFeed.slice(0, 5) : [{ iconName: "refresh-cw", title: "暂无操作记录", meta: "audit_logs 聚合待接入" }]} />
      </div>

      {/* Footer 数据口径 */}
      <div className="mt-10 border-t border-[var(--line2)] pt-4">
        <button type="button" onClick={() => setFootOpen(!footOpen)} className="border-0 bg-transparent text-[11px] text-[var(--mut)] cursor-pointer inline-flex items-center gap-1.5 hover:text-[var(--text)] transition-colors font-sans tracking-wide">
          数据口径 <span className={`text-[9px] transition-transform ${footOpen ? "rotate-180" : ""}`}>▾</span>
        </button>
        {footOpen && (
          <div className="mt-3 text-[11px] leading-relaxed text-[var(--mut)]">
            主轴数据来自后端 <span className="font-semibold">GET /dashboard/stats</span> 真实字段（knowledge_base_count、documents_by_status、ingestion_success_rate、total_chunk_count、chat_message_count、golden_hit_rate_percent 等）。
            标注「待聚合」的项需后端支撑：近 7 日按日分桶（提问趋势）、格式分布聚合（知识构成）、ChatMessage threads 列表。
          </div>
        )}
      </div>

      <Toast message={toast?.message ?? null} onDismiss={dismissToast} />
    </div>
  );
}
