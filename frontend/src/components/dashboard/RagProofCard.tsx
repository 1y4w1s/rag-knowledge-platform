interface RagProofCardProps {
  hitRate: number | null;
  evaluatedAt: string | null;
  note?: string;
}

export function RagProofCard({ hitRate, evaluatedAt, note }: RagProofCardProps) {
  const pct = hitRate !== null ? `${hitRate}%` : "—";
  const width = hitRate !== null ? `${Math.min(hitRate, 100)}%` : "0%";
  const dateStr = evaluatedAt
    ? `评估于 ${evaluatedAt.slice(0, 10)}`
    : "";

  return (
    <div className="h-full rounded-2xl border border-[var(--line2)] bg-[var(--surf)] px-0 py-2 shadow-[var(--top-hi),var(--card-shadow)] transition-colors hover:border-[var(--line)]">
      <div className="mb-4 text-center text-[13px] text-[var(--mut)]">
        检索可证明性 · Golden Hit@3
      </div>
      <div className="text-center">
        <div className="font-[var(--serif)] text-[46px] font-bold leading-none text-[var(--ok)] tabular-nums">
          {pct}
        </div>
        <div className="mt-2 text-xs text-[var(--mut)]">
          生产基线命中率 · {dateStr}
        </div>
        {/* gauge */}
        <div className="mx-auto mt-4 mb-2 h-[7px] w-full overflow-hidden rounded-full bg-[var(--surf2)]">
          <div
            className="block h-full bg-[var(--ok)]"
            style={{ width }}
          />
        </div>
        {note && (
          <div className="mt-2 text-xs text-[var(--mut)]">{note}</div>
        )}
      </div>
    </div>
  );
}
