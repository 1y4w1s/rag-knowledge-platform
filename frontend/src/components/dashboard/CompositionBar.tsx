interface CompItem {
  name: string;
  count: number;
  percent: number;
}

interface CompositionBarProps {
  items: CompItem[];
  totalLabel?: string;
  totalValue?: string;
  chunkCount?: string;
}

export function CompositionBar({
  items,
  totalLabel = "文档总数",
  totalValue,
  chunkCount,
}: CompositionBarProps) {
  return (
    <div className="dash-panel">
      <div className="mb-3 text-[13px] text-[var(--mut)]">知识构成</div>

      {items.length === 0 ? (
        <p className="py-4 text-sm text-muted">暂无格式分布</p>
      ) : (
        <div>
          {items.map(({ name, count, percent }) => (
            <div
              key={name}
              className="flex items-center gap-3 py-2 text-[13px]"
            >
              <span className="w-[72px] shrink-0 text-muted">{name}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surf2)]">
                <div
                  className="block h-full rounded-full bg-[color:color-mix(in_srgb,var(--action)_55%,#3a322c)]"
                  style={{ width: `${percent}%` }}
                />
              </div>
              <span className="w-10 shrink-0 text-right font-[var(--serif)] font-semibold tabular-nums">
                {count}
              </span>
            </div>
          ))}
        </div>
      )}

      {(totalValue || chunkCount) && (
        <div className="mt-4 flex gap-5 border-t border-[var(--line2)] pt-3">
          {totalValue ? (
            <div>
              <div className="font-[var(--serif)] text-2xl font-semibold">
                {totalValue}
              </div>
              <div className="mt-1 text-xs text-muted">{totalLabel}</div>
            </div>
          ) : null}
          {chunkCount ? (
            <div>
              <div className="font-[var(--serif)] text-2xl font-semibold">
                {chunkCount}
              </div>
              <div className="mt-1 text-xs text-muted">切片数</div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
