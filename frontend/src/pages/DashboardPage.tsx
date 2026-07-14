import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { DashboardDocumentSearch } from "@/components/dashboard/DashboardDocumentSearch";
import { DashboardOpsMetrics } from "@/components/dashboard/DashboardOpsMetrics";
import { EmptyStateV44, DASHBOARD_SCENE } from "@/components/ui/EmptyState";
import { DashboardRagMetrics } from "@/components/dashboard/DashboardRagMetrics";
import { DashboardStatsGrid } from "@/components/dashboard/DashboardStatsGrid";
import { DashboardStatusBanner } from "@/components/dashboard/DashboardStatusBanner";
import { DashboardZoneA } from "@/components/dashboard/DashboardZoneA";
import { StatCardSkeleton } from "@/components/dashboard/StatCard";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { Toast, useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth-context";
import { Reveal } from "@/components/common/Reveal";
import { CountUp } from "@/components/common/CountUp";
import {
  fetchDashboardStats,
  isDashboardEmpty,
  type DashboardStats,
} from "@/lib/dashboard-api";
import { canUseTeamBusiness, canWriteKnowledgeBase, isTeamMemberReadOnly } from "@/lib/org-permissions";
import { showMemberWriteBlockedToast } from "@/lib/member-write-message";
import { useDepartment } from "@/lib/department-context";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";
import { useWorkspace } from "@/lib/workspace-context";
import { opsMetricsFromStats } from "@/lib/ops-metrics";
import { ragMetricsFromStats } from "@/lib/rag-metrics";

function StatsSkeletonRow() {
  return (
    <div>
      <div className="mb-2.5 h-4 w-16 animate-pulse rounded bg-border/80" />
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        {["资料库", "已上传文件", "已可提问文件", "近 7 日提问"].map(
          (label) => (
            <StatCardSkeleton key={label} label={label} />
          ),
        )}
      </div>
    </div>
  );
}

function DashboardHeroCard({
  nickname,
  stats,
}: {
  nickname?: string | null;
  stats: DashboardStats | null;
}) {
  return (
    <section
      className="relative overflow-hidden rounded-2xl p-6 text-white shadow-[var(--shadow-xl)] sm:p-7"
      style={{ backgroundImage: "var(--brand-grad-deep)" }}
    >
      <div className="hero-aurora" aria-hidden />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            "radial-gradient(130% 130% at 100% 0%, rgba(255,255,255,0.4), rgba(255,255,255,0) 55%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-50"
        style={{
          backgroundImage:
            "linear-gradient(90deg, rgba(60,22,8,0.58) 0%, rgba(60,22,8,0.22) 45%, transparent 70%)",
        }}
      />
      <div className="relative z-10 flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-[0.78rem] font-medium text-white/90">欢迎回来</p>
          <h2 className="mt-1 font-serif text-[1.55rem] font-bold leading-tight sm:text-[1.75rem]">
            {nickname?.trim() || "朋友"}，今天想聊点什么？
          </h2>
          <p className="mt-2 max-w-[42ch] text-sm text-white/90">
            在资料库中提问，每条回答都附带可展开的引用来源与页码定位。
          </p>
          <div className="mt-4 flex gap-3">
            <Link
              to="/ask"
              className="btn-shine inline-flex items-center rounded-[10px] bg-white/15 px-4 py-2 text-sm font-medium text-white ring-1 ring-white/30 transition-colors hover:bg-white/25"
            >
              开始提问 ›
            </Link>
          </div>
        </div>
        <div className="flex shrink-0 gap-7">
          <div className="text-right">
            <div className="font-mono text-[1.7rem] font-bold leading-none tabular-nums">
              {stats ? <CountUp value={stats.knowledge_base_count} /> : "—"}
            </div>
            <div className="mt-1 text-xs text-white/75">资料库</div>
          </div>
          <div className="text-right">
            <div className="font-mono text-[1.7rem] font-bold leading-none tabular-nums">
              {stats ? <CountUp value={stats.chat_message_count} /> : "—"}
            </div>
            <div className="mt-1 text-xs text-white/75">近 7 日提问</div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function DashboardPage() {
  const navigate = useNavigate();
  const { user, isOrgAdmin } = useAuth();
  const { workspace, generation, getGeneration } = useWorkspace();
  const {
    departmentId,
    generation: departmentGeneration,
    getGeneration: getDepartmentGeneration,
  } = useDepartment();
  const { toast, show: showToast, dismiss: dismissToast } = useToast();
  const { setOverride } = useShellBreadcrumb();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    const expectedGen = generation;
    const expectedDeptGen = departmentGeneration;
    const requestWorkspace = workspace;
    const requestDepartmentId = workspace === "personal" ? null : departmentId;
    setLoading(true);
    setError(null);
    setStats(null);
    try {
      const data = await fetchDashboardStats({
        expectedGen,
        getCurrentGeneration: getGeneration,
        expectedDepartmentGen: expectedDeptGen,
        getCurrentDepartmentGeneration: getDepartmentGeneration,
        workspace: requestWorkspace,
        departmentId: requestDepartmentId,
      });
      if (data === null) return;
      if (getGeneration() !== expectedGen) return;
      if (getDepartmentGeneration() !== expectedDeptGen) return;
      setStats(data);
    } catch (err) {
      if (getGeneration() !== expectedGen) return;
      if (getDepartmentGeneration() !== expectedDeptGen) return;
      setStats(null);
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      if (
        getGeneration() === expectedGen &&
        getDepartmentGeneration() === expectedDeptGen
      ) {
        setLoading(false);
      }
    }
  }, [
    workspace,
    generation,
    getGeneration,
    departmentId,
    departmentGeneration,
    getDepartmentGeneration,
  ]);

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  useEffect(() => {
    setOverride(null);
    document.title = "睿阁 · 概览";
  }, [setOverride]);

  const isEmpty = stats !== null && isDashboardEmpty(stats);
  const canWriteKb = canWriteKnowledgeBase(user, workspace);
  const teamBusinessAllowed = canUseTeamBusiness(user, workspace);
  const isMemberReadOnly = isTeamMemberReadOnly(user, workspace);
  const notifyMemberWriteBlocked = useCallback(() => {
    showMemberWriteBlockedToast(showToast);
  }, [showToast]);

  const ragMetrics = useMemo(() => {
    if (!stats || isEmpty) return null;
    return ragMetricsFromStats(stats);
  }, [stats, isEmpty]);

  const opsMetrics = useMemo(() => {
    if (!stats || isEmpty) return null;
    return opsMetricsFromStats(stats);
  }, [stats, isEmpty]);

  return (
    <div className="floating-sheet mx-auto flex w-full max-w-[1320px] flex-col gap-5 p-6 min-h-[calc(100vh-9rem)]">
      <DashboardHeroCard nickname={user?.nickname} stats={stats} />
      {error && (
        <AlertBanner
          action={
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={loadStats}
            >
              重试
            </Button>
          }
        >
          {error}
        </AlertBanner>
      )}

      <Reveal variant="up">
        <DashboardDocumentSearch
          expectedGen={generation}
          getCurrentGeneration={getGeneration}
          expectedDepartmentGen={departmentGeneration}
          getCurrentDepartmentGeneration={getDepartmentGeneration}
          workspace={workspace}
          departmentId={workspace === "personal" ? null : departmentId}
        />
      </Reveal>

      {loading ? (
        <>
          <div className="h-[140px] animate-pulse rounded-xl border border-border bg-white/60" />
          <StatsSkeletonRow />
        </>
      ) : stats ? (
        <>
          <Reveal variant="up" delay={60}>
            <DashboardZoneA
              isEmpty={isEmpty}
              recentKbId={stats.recent_kb_id}
              statsScope={stats.scope}
              isOrgAdmin={isOrgAdmin}
              memberCount={stats.member_count}
              canWriteKb={canWriteKb}
              canUseTeamBusiness={teamBusinessAllowed}
              onMemberWriteBlocked={
                isMemberReadOnly ? notifyMemberWriteBlocked : undefined
              }
            />
          </Reveal>
          {!isEmpty && (
            <Reveal variant="up" delay={80}>
              <DashboardStatusBanner
                stats={stats}
                recentKbId={stats.recent_kb_id}
                workspace={workspace}
                canWriteKb={canWriteKb}
                onShowToast={showToast}
              />
            </Reveal>
          )}
          <DashboardStatsGrid
            stats={stats}
            recentKbId={stats.recent_kb_id}
            dim={isEmpty}
            emptyNote={
              isEmpty
                ? "上传并整理后，统计与问答能力数据会自动更新。"
                : null
            }
          />
          {isEmpty ? (
            <EmptyStateV44
              scene={{
                ...DASHBOARD_SCENE,
                ctaPrimary: {
                  ...DASHBOARD_SCENE.ctaPrimary,
                  onClick: () => navigate("/knowledge-bases"),
                },
                ctaSecondary: {
                  ...DASHBOARD_SCENE.ctaSecondary,
                  onClick: () => navigate("/knowledge-bases"),
                },
              }}
            />
          ) : (
            <>
              {opsMetrics && (
                <Reveal variant="up" delay={120}>
                  <DashboardOpsMetrics metrics={opsMetrics} />
                </Reveal>
              )}
              {ragMetrics && (
                <Reveal variant="up" delay={140}>
                  <DashboardRagMetrics metrics={ragMetrics} />
                </Reveal>
              )}
            </>
          )}
        </>
      ) : null}

      <Toast message={toast?.message ?? null} onDismiss={dismissToast} />
    </div>
  );
}
