interface RagProofCardProps {
  hitRate: number | null;
  evaluatedAt: string | null;
  note?: string;
}

export function RagProofCard({ hitRate, evaluatedAt, note }: RagProofCardProps) {
  const pct = hitRate !== null ? `${hitRate}%` : "—";
  const width = hitRate !== null ? `${Math.min(hitRate, 100)}%` : "0%";
  const dateStr = evaluatedAt ? `评估于 ${evaluatedAt.slice(0, 10)}` : "";

  return (
    <div className="dash-panel h-full text-center">
      <div className="mb-3 text-[13px] text-[var(--mut)]">
        检索可证明性 · Hit@3
      </div>
      <div className="font-[var(--serif)] text-[2.125rem] font-bold leading-none text-[var(--ok)] tabular-nums">
        {pct}
      </div>
      <div className="mt-2 text-xs text-muted">
        {note ?? "评测基线命中率"}
        {dateStr ? ` · ${dateStr}` : ""}
      </div>
      <div className="mx-auto mt-4 h-[7px] w-full overflow-hidden rounded-full bg-[var(--surf2)]">
        <div className="block h-full bg-[var(--ok)]" style={{ width }} />
      </div>
    </div>
  );
}
