interface CompItem {
  name: string;
  count: number;
  percent: number; // 0-100
}

interface CompositionBarProps {
  items: CompItem[];
  totalLabel?: string;
  totalValue?: string;
  chunkCount?: string;
}

export function CompositionBar({
  items,
  totalLabel = "知识总体积",
  totalValue,
  chunkCount,
}: CompositionBarProps) {
  return (
    <div className="rounded-2xl border border-[var(--line2)] bg-[var(--surf)] p-5 shadow-[var(--top-hi),var(--card-shadow)] transition-colors hover:border-[var(--line)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className="text-[13px] text-[var(--mut)] tracking-wide">知识构成</span>
        <span className="rounded-[6px] border border-[var(--line2)] px-[7px] py-[2px] text-[10px] text-[var(--mut)] tracking-wider">
          格式分布
        </span>
      </div>

      {/* 进度条行 */}
      <div>
        {items.map(({ name, count, percent }) => (
          <div key={name} className="flex items-center gap-3 py-[9px] text-[13px]">
            <span className="w-[84px] shrink-0 text-[var(--mut)]">{name}</span>
            <div className="h-[9px] flex-1 overflow-hidden rounded-full bg-[var(--surf2)]">
              <i
                className="block h-full rounded-full bg-[var(--ink)]"
                style={{ width: `${percent}%` }}
              />
            </div>
            <span className="w-[44px] shrink-0 text-right font-[var(--serif)] font-semibold tabular-nums">
              {count}
            </span>
          </div>
        ))}
      </div>

      {/* 底部汇总 */}
      {(totalValue || chunkCount) && (
        <div className="mt-4 flex gap-6 border-t border-[var(--line2)] pt-4">
          {totalValue && (
            <div>
              <div className="font-[var(--serif)] text-2xl font-semibold">{totalValue}</div>
              <div className="mt-1 text-[11px] text-[var(--mut)]">{totalLabel}</div>
            </div>
          )}
          {chunkCount && (
            <div>
              <div className="font-[var(--serif)] text-2xl font-semibold">{chunkCount}</div>
              <div className="mt-1 text-[11px] text-[var(--mut)]">切片颗粒</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
