import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SlidersHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  buildUrlWithDocumentListFilters,
  DOCUMENT_FORMAT_OPTIONS,
  DOCUMENT_STATUS_OPTIONS,
  parseDocumentListFilters,
  type DocumentFormatFilter,
  type DocumentListFilters,
  type DocumentStatusGroup,
} from "@/lib/document-advanced-filter";
import { cn } from "@/lib/utils";

interface DocumentAdvancedFilterProps {
  pathname: string;
  search: string;
}

function toggleValue<T extends string>(values: T[] | null | undefined, value: T): T[] {
  const safe = Array.isArray(values) ? values : [];
  return safe.includes(value)
    ? safe.filter((item) => item !== value)
    : [...safe, value];
}

export function DocumentAdvancedFilter({
  pathname,
  search,
}: DocumentAdvancedFilterProps) {
  const navigate = useNavigate();
  const activeFilters = useMemo(
    () => parseDocumentListFilters(search),
    [search],
  );
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DocumentListFilters>(activeFilters);

  useEffect(() => {
    setDraft(activeFilters);
  }, [activeFilters]);

  function updateDraft(partial: Partial<DocumentListFilters>) {
    setDraft((prev) => ({ ...prev, ...partial }));
  }

  function toggleFormat(format: DocumentFormatFilter) {
    updateDraft({ formats: toggleValue(draft.formats, format) });
  }

  function toggleStatus(status: DocumentStatusGroup) {
    updateDraft({ statuses: toggleValue(draft.statuses, status) });
  }

  function applyFilters() {
    navigate(buildUrlWithDocumentListFilters(pathname, search, draft), {
      replace: true,
    });
    setOpen(false);
  }

  function resetDraft() {
    const empty: DocumentListFilters = {
      formats: [],
      statuses: [],
      uploadedFrom: null,
      uploadedTo: null,
    };
    setDraft(empty);
    navigate(buildUrlWithDocumentListFilters(pathname, search, empty), {
      replace: true,
    });
    setOpen(false);
  }

  const activeCount =
    activeFilters.formats.length +
    activeFilters.statuses.length +
    (activeFilters.uploadedFrom ? 1 : 0) +
    (activeFilters.uploadedTo ? 1 : 0);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className={cn(
          "kb-sort-pill inline-flex items-center gap-1.5",
          activeCount > 0 ? "kb-sort-pill-active" : "kb-sort-pill-idle",
        )}
        aria-expanded={open}
        aria-controls="document-advanced-filter-panel"
      >
        <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden />
        筛选
        {activeCount > 0 ? (
          <span className="rounded-full bg-[var(--action)] px-1.5 text-[0.65rem] text-white">
            {activeCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          id="document-advanced-filter-panel"
          className="absolute left-0 top-[calc(100%+0.5rem)] z-20 w-[min(22rem,calc(100vw-2rem))] rounded-2xl border border-[var(--line2)] bg-[var(--bg)] p-4 shadow-[var(--card-shadow)]"
        >
          <div className="space-y-4">
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-muted">
                格式
              </legend>
              <div className="flex flex-wrap gap-2">
                {DOCUMENT_FORMAT_OPTIONS.map(({ value, label }) => {
                  const checked = draft.formats.includes(value);
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => toggleFormat(value)}
                      className={cn(
                        "kb-sort-pill",
                        checked ? "kb-sort-pill-active" : "kb-sort-pill-idle",
                      )}
                      aria-pressed={checked}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <fieldset>
              <legend className="mb-2 text-xs font-medium text-muted">
                状态
              </legend>
              <div className="flex flex-wrap gap-2">
                {DOCUMENT_STATUS_OPTIONS.map(({ value, label }) => {
                  const checked = draft.statuses.includes(value);
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => toggleStatus(value)}
                      className={cn(
                        "kb-sort-pill",
                        checked ? "kb-sort-pill-active" : "kb-sort-pill-idle",
                      )}
                      aria-pressed={checked}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <fieldset>
              <legend className="mb-2 text-xs font-medium text-muted">
                上传日期
              </legend>
              <div className="grid grid-cols-2 gap-2">
                <label className="space-y-1 text-xs text-muted">
                  <span>起</span>
                  <input
                    type="date"
                    value={draft.uploadedFrom ?? ""}
                    onChange={(event) =>
                      updateDraft({
                        uploadedFrom: event.target.value || null,
                      })
                    }
                    className="w-full rounded-lg border border-[var(--line2)] px-2 py-1.5 text-sm text-foreground"
                  />
                </label>
                <label className="space-y-1 text-xs text-muted">
                  <span>止</span>
                  <input
                    type="date"
                    value={draft.uploadedTo ?? ""}
                    onChange={(event) =>
                      updateDraft({
                        uploadedTo: event.target.value || null,
                      })
                    }
                    className="w-full rounded-lg border border-[var(--line2)] px-2 py-1.5 text-sm text-foreground"
                  />
                </label>
              </div>
            </fieldset>
          </div>

          <div className="mt-4 flex items-center justify-end gap-2">
            <Button type="button" variant="outline" size="sm" onClick={resetDraft}>
              清除
            </Button>
            <Button type="button" size="sm" onClick={applyFilters}>
              应用
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
