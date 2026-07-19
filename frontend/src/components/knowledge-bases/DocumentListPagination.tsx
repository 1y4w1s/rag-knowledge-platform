import { useState } from "react";

import { Button } from "@/components/ui/button";

type DocumentListPaginationProps = {
  page: number;
  pageCount: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  itemUnit?: string;
  showPageJump?: boolean;
};

function clampPage(target: number, pageCount: number): number {
  return Math.min(Math.max(Math.trunc(target), 1), pageCount);
}

export function DocumentListPagination({
  page,
  pageCount,
  total,
  pageSize,
  onPageChange,
  itemUnit = "篇",
  showPageJump = true,
}: DocumentListPaginationProps) {
  const [jumpDraft, setJumpDraft] = useState("");

  if (total <= pageSize) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  function submitJump() {
    const parsed = Number.parseInt(jumpDraft.trim(), 10);
    if (!Number.isFinite(parsed)) return;
    onPageChange(clampPage(parsed, pageCount));
    setJumpDraft("");
  }

  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--line2)] pt-4">
      <p className="text-sm text-[var(--mut)]">
        第 {start}–{end} 条，共 {total} {itemUnit}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          上一页
        </Button>
        <span className="min-w-[4.5rem] text-center text-sm text-[var(--mut)]">
          {page} / {pageCount}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          下一页
        </Button>
        {showPageJump && pageCount > 1 && (
          <form
            className="flex items-center gap-1.5"
            onSubmit={(event) => {
              event.preventDefault();
              submitJump();
            }}
          >
            <label htmlFor="list-page-jump" className="text-sm text-[var(--mut)]">
              跳至
            </label>
            <input
              id="list-page-jump"
              type="number"
              min={1}
              max={pageCount}
              inputMode="numeric"
              value={jumpDraft}
              onChange={(event) => setJumpDraft(event.target.value)}
              placeholder={String(page)}
              aria-label={`跳转到第几页，共 ${pageCount} 页`}
              className="h-8 w-16 rounded-[8px] border border-[var(--line2)] bg-[var(--surf)] px-2 text-center text-sm text-foreground outline-none transition-colors focus:border-[var(--action)] focus:ring-1 focus:ring-[var(--action)]"
            />
            <span className="text-sm text-[var(--mut)]">页</span>
            <Button type="submit" variant="outline" size="sm">
              跳转
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
