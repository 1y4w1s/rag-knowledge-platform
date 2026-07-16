import { X } from "lucide-react";
import { Link } from "react-router-dom";

import { KbResultEmptyPanel } from "@/components/knowledge-bases/KbResultEmptyPanel";
import { Button } from "@/components/ui/button";
import {
  getStatusFilterLabel,
  type DocumentStatusFilter,
} from "@/lib/document-status-filter";
import {
  getFilterEmptyDescription,
  getFilterEmptyTitle,
} from "@/lib/kb-empty-copy";
import { cn } from "@/lib/utils";

interface DocumentStatusFilterBarProps {
  filter: DocumentStatusFilter;
  clearTo: string;
}

const FILTER_DOT_CLASS: Record<DocumentStatusFilter, string> = {
  processing: "bg-[var(--action)]",
  failed: "bg-[var(--bad)]",
};

const FILTER_PILL_CLASS: Record<DocumentStatusFilter, string> = {
  processing: "status-filter-pill-proc",
  failed: "status-filter-pill-err",
};

const FILTER_BTN_CLASS: Record<DocumentStatusFilter, string> = {
  processing: "border-[#E8C4B0] text-[#8B4513]",
  failed: "border-[var(--status-err-border)] text-[var(--status-err-text)]",
};

export function DocumentStatusFilterBar({
  filter,
  clearTo,
}: DocumentStatusFilterBarProps) {
  return (
    <div
      className={cn(
        "inline-flex flex-wrap items-center gap-2 rounded-full border px-3 py-1.5 text-sm",
        FILTER_PILL_CLASS[filter],
      )}
      role="status"
      aria-live="polite"
    >
      <span
        className={cn("h-1.5 w-1.5 shrink-0 rounded-full", FILTER_DOT_CLASS[filter])}
        aria-hidden
      />
      <span>
        正在筛选：
        <strong className="font-medium">{getStatusFilterLabel(filter)}</strong>
      </span>
      <Button
        asChild
        type="button"
        variant="outline"
        size="sm"
        className={cn(
          "h-6 rounded-full bg-white/80 px-2.5 text-[0.75rem] transition-colors duration-200 hover:bg-white",
          FILTER_BTN_CLASS[filter],
        )}
      >
        <Link to={clearTo} aria-label="清除状态筛选">
          <X className="mr-1 h-3 w-3" aria-hidden />
          清除筛选
        </Link>
      </Button>
    </div>
  );
}

interface DocumentFilterEmptyPanelProps {
  filter: DocumentStatusFilter;
  clearTo: string;
}

export function DocumentFilterEmptyPanel({
  filter,
  clearTo,
}: DocumentFilterEmptyPanelProps) {
  return (
    <KbResultEmptyPanel
      title={getFilterEmptyTitle(filter)}
      description={getFilterEmptyDescription(filter)}
      live
      action={
        <Button
          asChild
          type="button"
          variant="outline"
          size="sm"
          className="kb-result-empty-clear"
        >
          <Link to={clearTo}>清除筛选</Link>
        </Button>
      }
    />
  );
}
