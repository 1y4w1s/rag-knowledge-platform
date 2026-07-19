import {
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

  return (
    <button
      type="button"
      className={`cite-chip${active ? " cite-chip-active" : ""}${
        unavailable ? " cite-chip-inaccessible" : ""
      }`}
      onClick={onClick}
      aria-pressed={active}
      disabled={expandBlocked}
      title={title}
    >
      <span className="cite-chip-num">{index}</span>
      {formatCitationLabel(citation, mode)}
    </button>
  );
}
