import { Link } from "react-router-dom";

import { KbResultEmptyPanel } from "@/components/knowledge-bases/KbResultEmptyPanel";
import { Button } from "@/components/ui/button";
import {
  describeActiveListFilters,
  type DocumentListFilters,
} from "@/lib/document-advanced-filter";
import { getAdvancedFilterEmptyCopy } from "@/lib/kb-empty-copy";

interface DocumentListFiltersEmptyPanelProps {
  filters: DocumentListFilters;
  clearTo: string;
}

export function DocumentListFiltersEmptyPanel({
  filters,
  clearTo,
}: DocumentListFiltersEmptyPanelProps) {
  const summary = describeActiveListFilters(filters).join(" · ");
  const { title, description } = getAdvancedFilterEmptyCopy(summary);

  return (
    <KbResultEmptyPanel
      title={title}
      description={description}
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
