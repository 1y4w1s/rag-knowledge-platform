import {
  citationChipStatusLabel,
  citationChipTitle,
  formatCitationLabel,
  isCitationChipUnavailable,
  isCitationExpandBlocked,
  type Citation,
  type CitationLabelMode,
} from "@/lib/chat-api";

interface CitationChipProps {
  index: number;
  citation: Citation;
  active?: boolean;
  mode?: CitationLabelMode;
  onClick: () => void;
}

export function CitationChip({
  index,
  citation,
  active,
  mode = "kb",
  onClick,
}: CitationChipProps) {
  const unavailable = isCitationChipUnavailable(citation);
  const expandBlocked = isCitationExpandBlocked(citation);
  const title = citationChipTitle(citation);
  const statusLabel = citationChipStatusLabel(citation);
  const staleClass =
    citation.source_status === "chunk_stale" && !expandBlocked
      ? " cite-chip-stale"
      : unavailable
        ? " cite-chip-inaccessible"
        : "";

  return (
    <button
      type="button"
      className={`cite-chip${active ? " cite-chip-active" : ""}${staleClass}`}
      onClick={onClick}
      aria-pressed={active}
      disabled={expandBlocked}
      title={title}
      data-testid="citation-chip"
      data-source-status={citation.source_status ?? "available"}
    >
      <span className="cite-chip-num">{index}</span>
      {formatCitationLabel(citation, mode)}
      {statusLabel && (
        <span className="cite-chip-status" data-testid="citation-chip-status">
          {statusLabel}
        </span>
      )}
    </button>
  );
}
