import { useCallback, useEffect, useState } from "react";

import type { SelectOption } from "@/components/ui/Select";
import { fetchKnowledgeBases } from "@/lib/knowledge-base-api";
import { fetchOrganizationMembers } from "@/lib/organization-api";
import { useWorkspace } from "@/lib/workspace-context";

function sortOptions(options: SelectOption[]): SelectOption[] {
  return [...options].sort((a, b) => a.label.localeCompare(b.label, "zh-CN"));
}

/** 审计页：资料库 / 成员筛选下拉选项 */
export function useAuditFilterOptions() {
  const { workspace, generation, getGeneration } = useWorkspace();
  const [kbOptions, setKbOptions] = useState<SelectOption[]>([]);
  const [actorOptions, setActorOptions] = useState<SelectOption[]>([]);

  const load = useCallback(async () => {
    try {
      const [kbs, members] = await Promise.all([
        fetchKnowledgeBases({
          workspace,
          expectedGen: generation,
          getCurrentGeneration: getGeneration,
        }),
        fetchOrganizationMembers(),
      ]);
      if (kbs) {
        setKbOptions(
          sortOptions(kbs.map((kb) => ({ value: kb.id, label: kb.name }))),
        );
      }
      setActorOptions(
        sortOptions(
          members.map((m) => ({ value: m.user_id, label: m.email })),
        ),
      );
    } catch {
      /* 筛选下拉失败不挡主列表 */
    }
  }, [workspace, generation, getGeneration]);

  useEffect(() => {
    void load();
  }, [load]);

  return { kbOptions, actorOptions };
}
