import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { VitalCard } from "@/components/dashboard/VitalCard";
import { IngestionPanel } from "@/components/dashboard/IngestionPanel";
import { RagProofCard } from "@/components/dashboard/RagProofCard";
import { PerfTable } from "@/components/dashboard/PerfTable";
import { ActivityChart } from "@/components/dashboard/ActivityChart";
import { CompositionBar } from "@/components/dashboard/CompositionBar";
import { FeedList } from "@/components/dashboard/FeedList";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
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
import { useDepartment } from "@/lib/department-context";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";
import { useWorkspace } from "@/lib/workspace-context";
import { SectionTitle } from "@/components/common/SectionTitle";

export function DashboardPage() {
  const navigate = useNavigate();
  const { workspace, generation, getGeneration } = useWorkspace();
  const {
    departmentId,
    generation: deptGen,
    getGeneration: getDeptGen,
  } = useDepartment();
  const { setOverride } = useShellBreadcrumb();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    const eg = generation;
    const ed = deptGen;
    setLoading(true);
    setError(null);
    setStats(null);
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
      setStats(data);
    } catch (err) {
      if (getGeneration() !== eg || getDeptGen() !== ed) return;
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      if (getGeneration() === eg && getDeptGen() === ed) setLoading(false);
    }
  }, [workspace, generation, getGeneration, departmentId, deptGen, getDeptGen]);

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  useEffect(() => {
    setOverride(null);
    document.title = "睿阁 · 概览";
  }, [setOverride]);

  const isEmpty = stats !== null && isDashboardEmpty(stats);

  const threadFeed = useMemo(
    () => (stats ? mapThreadsToFeed(stats.recent_threads) : []),
    [stats],
  );
  const actFeed = useMemo(
    () => (stats ? mapActivitiesToFeed(stats.recent_activities).slice(0, 5) : []),
    [stats],
  );

  if (loading) {
    return (
      <div className="dash-page mx-auto w-full max-w-[1180px] px-7 pb-16 pt-7">
        <div className="mb-4 h-8 w-28 animate-pulse rounded bg-border/70" />
        <div className="mb-4 h-12 animate-pulse rounded-xl border border-[var(--line2)] bg-white/60" />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-[100px] animate-pulse rounded-[14px] border border-[var(--line2)] bg-white/60"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-[1180px] px-7 pb-16 pt-7">
        <AlertBanner
          action={
            <Button type="button" variant="outline" size="sm" onClick={loadStats}>
              重试
            </Button>
          }
        >
          {error}
        </AlertBanner>
      </div>
    );
  }

  if (!stats || isEmpty) {
    return (
      <div className="dash-page mx-auto max-w-[1180px] px-7 pb-16 pt-7">
        <SectionTitle label="概览" en="OVERVIEW" tone="quiet" />
        <div className="dash-empty">
          <h2 className="font-[var(--serif)] text-[1.375rem] font-bold text-foreground">
            还没有可问的知识
          </h2>
          <p className="mt-2 max-w-[420px] text-sm leading-relaxed text-muted">
            新建资料库并上传文档后，这里会显示就绪状态与最近提问。
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
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
              variant="ghost"
              className="text-[var(--action)]"
              onClick={() => navigate("/ask")}
            >
              去对话看看
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const ds = stats.documents_by_status;
  const failedHref = stats.recent_kb_id
    ? `/knowledge-bases/${stats.recent_kb_id}`
    : "/knowledge-bases";

  return (
    <div className="dash-page mx-auto w-full max-w-[1180px] px-7 pb-16 pt-7">
      <SectionTitle label="概览" en="OVERVIEW" tone="quiet" />

      <div className="dash-ready-strip" role="status">
        <span className="dash-ready-ok">{ds.completed} 篇可提问</span>
        {ds.failed > 0 ? (
          <>
            <span className="dash-ready-bad">{ds.failed} 篇失败 · 需处理</span>
            <Link to={failedHref} className="dash-ready-link">
              查看资料库
            </Link>
          </>
        ) : (
          <span className="text-xs text-muted">入库正常</span>
        )}
      </div>

      <section aria-label="关键指标" className="mb-2">
        <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
          <VitalCard
            value={stats.knowledge_base_count}
            label="资料库"
            hint="当前空间可见"
            href="/knowledge-bases"
          />
          <VitalCard
            value={stats.document_count}
            label="已入库文件"
            hint={`可提问 ${ds.completed}`}
            accent="ok"
            href={
              stats.recent_kb_id
                ? `/knowledge-bases/${stats.recent_kb_id}`
                : "/knowledge-bases"
            }
          />
          <VitalCard
            value={stats.chat_message_count}
            label="近 7 日提问"
            hint="含引用溯源"
            accent="info"
            href="/ask"
          />
          {stats.member_count !== null ? (
            <VitalCard
              value={stats.member_count}
              label="团队成员"
              hint="企业版"
              href="/organization/members"
            />
          ) : null}
        </div>
      </section>

      <section aria-label="最近提问" className="mt-7">
        <SectionTitle label="最近提问" en="RECENT" tone="quiet" />
        <FeedList
          title="带引用的对话"
          items={threadFeed}
          emptyText="暂无对话记录"
          variant="soft"
        />
      </section>

      <section aria-label="入库态势" className="mt-7">
        <SectionTitle label="入库态势" en="INGESTION" tone="quiet" />
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

      <section aria-label="可信与性能" className="mt-7">
        <SectionTitle label="可信与性能" en="TRUST" tone="quiet" />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <RagProofCard
            hitRate={stats.golden_hit_rate_percent}
            evaluatedAt={stats.golden_baseline_evaluated_at}
            note="评测基线命中率 · 回答有出处可抽检"
          />
          <PerfTable
            latency={stats.avg_retrieval_latency_ms}
            sampleCount={stats.retrieval_latency_sample_count}
          />
        </div>
      </section>

      <section aria-label="活跃度" className="mt-7">
        <SectionTitle label="活跃度" en="ACTIVITY" tone="quiet" />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-[1.4fr_1fr]">
          <ActivityChart points={stats.question_trend} />
          <CompositionBar
            items={stats.format_distribution.map((f) => ({
              name: f.format,
              count: f.count,
              percent:
                stats.document_count > 0
                  ? Math.round((f.count / stats.document_count) * 100)
                  : 0,
            }))}
            totalLabel="文档总数"
            totalValue={String(stats.document_count)}
            chunkCount={formatK(stats.total_chunk_count)}
          />
        </div>
      </section>

      <section aria-label="操作动态" className="mt-7">
        <SectionTitle label="操作动态" en="ACTIVITY LOG" tone="quiet" />
        <FeedList
          title="最近操作"
          items={actFeed}
          emptyText="暂无操作动态"
          emptyIcon="refresh-cw"
          variant="soft"
        />
      </section>

      <footer className="dash-foot">数据按当前空间实时汇总</footer>
    </div>
  );
}
