import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import type { DashboardStats } from "@/lib/dashboard-api";
import { cn } from "@/lib/utils";
import type { WorkspaceId } from "@/lib/workspace-storage";

function readyBannerDismissKey(workspace: WorkspaceId): string {
  return `dashboard-ready-banner-dismissed:${workspace}`;
}

interface DashboardStatusBannerProps {
  stats: DashboardStats;
  recentKbId: string | null;
  workspace: WorkspaceId;
  canWriteKb?: boolean;
  onShowToast?: (message: string) => void;
}

function statusHref(
  recentKbId: string | null,
  status: "processing" | "failed",
): string | null {
  if (!recentKbId) return null;
  return `/knowledge-bases/${recentKbId}?status=${status}`;
}

export function DashboardStatusBanner({
  stats,
  recentKbId,
  workspace,
  canWriteKb = true,
  onShowToast,
}: DashboardStatusBannerProps) {
  const navigate = useNavigate();
  const docStatus = stats.documents_by_status;
  const processingCount = docStatus.queued + docStatus.processing;
  const failedCount = docStatus.failed;
  const hasDocuments = stats.document_count > 0;
  const dismissKey = readyBannerDismissKey(workspace);

  const [readyDismissed, setReadyDismissed] = useState(() => {
    try {
      return localStorage.getItem(dismissKey) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      setReadyDismissed(localStorage.getItem(dismissKey) === "1");
    } catch {
      setReadyDismissed(false);
    }
  }, [dismissKey]);

  useEffect(() => {
    if (processingCount > 0 || failedCount > 0) {
      try {
        localStorage.removeItem(dismissKey);
      } catch {
        /* ignore */
      }
      setReadyDismissed(false);
    }
  }, [processingCount, failedCount, dismissKey]);

  function followStatusLink(status: "processing" | "failed") {
    const href = statusHref(recentKbId, status);
    if (href) {
      navigate(href);
      return;
    }
    onShowToast?.("请先创建资料库");
    navigate("/knowledge-bases");
  }

  if (failedCount > 0) {
    const href = statusHref(recentKbId, "failed");
    return (
      <AlertBanner
        action={
          href ? (
            <Button
              asChild
              variant="outline"
              size="sm"
              className="border-[var(--status-err-border)] bg-white/80 text-[var(--status-err-text)] hover:bg-white"
            >
              <Link to={href}>去处理</Link>
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="border-[var(--status-err-border)] bg-white/80 text-[var(--status-err-text)] hover:bg-white"
              onClick={() => followStatusLink("failed")}
            >
              去处理
            </Button>
          )
        }
      >
        <span>
          <span className="font-semibold">
            {failedCount} 份文件整理失败
          </span>
          <span className="mt-0.5 block text-[0.75rem] opacity-90">
            {canWriteKb
              ? "请在资料库中查看失败项并重试或重新上传"
              : "请在资料库中查看失败项，如需重试请联系管理员"}
          </span>
        </span>
      </AlertBanner>
    );
  }

  if (processingCount > 0) {
    const href = statusHref(recentKbId, "processing");
    return (
      <div className="alert-banner-proc rounded-[10px] border px-4 py-3 text-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-semibold">
              {processingCount} 份文件正在整理
            </p>
            <p className="mt-0.5 text-[0.75rem] opacity-90">
              解析与向量化完成后即可提问
            </p>
          </div>
          {href ? (
            <Button
              asChild
              variant="outline"
              size="sm"
              className="shrink-0 border-[#E8C4B0] bg-white/80 text-[#8B4513] hover:bg-white"
            >
              <Link to={href}>查看进度</Link>
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0 border-[#E8C4B0] bg-white/80 text-[#8B4513] hover:bg-white"
              onClick={() => followStatusLink("processing")}
            >
              查看进度
            </Button>
          )}
        </div>
        <div
          className="mt-2.5 h-1 overflow-hidden rounded-full bg-[rgba(139,69,19,0.15)]"
          aria-hidden
        >
          <div className="banner-progress-indeterminate h-full rounded-full bg-[var(--action)]" />
        </div>
      </div>
    );
  }

  if (hasDocuments && !readyDismissed) {
    return (
      <div className="alert-banner-ready rounded-[10px] border px-4 py-3 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-semibold">全部文件已就绪</p>
            <p className="mt-0.5 text-[0.75rem] opacity-90">
              {docStatus.completed} 份文件可直接提问
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className={cn(
              "h-7 border-[#D4CCC4] bg-white/80 px-2 text-[#524A44] hover:bg-white",
            )}
            onClick={() => {
              try {
                localStorage.setItem(dismissKey, "1");
              } catch {
                /* ignore */
              }
              setReadyDismissed(true);
            }}
            aria-label="关闭提示"
          >
            ×
          </Button>
        </div>
      </div>
    );
  }

  return null;
}
