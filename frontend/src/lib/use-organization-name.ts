import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { fetchOrganizationSettings } from "@/lib/organization-api";

const ORG_NAME_CHANGED = "ruige:org-name-changed";

/** 触发全局刷新：所有 useOrganizationName 消费方将重新获取。 */
export function triggerOrgNameRefresh(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(ORG_NAME_CHANGED));
  }
}

/** Fetches org display name for sidebar (H4 · W2). Cached per mount / org_id change / refresh event. */
export function useOrganizationName(): { name: string; loading: boolean } {
  const { user } = useAuth();
  const orgId = user?.org_id ?? null;
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // 监听全局刷新事件
  useEffect(() => {
    const handler = () => setRefreshKey((k) => k + 1);
    window.addEventListener(ORG_NAME_CHANGED, handler);
    return () => window.removeEventListener(ORG_NAME_CHANGED, handler);
  }, []);

  useEffect(() => {
    if (!orgId) {
      setName("");
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    void fetchOrganizationSettings()
      .then((settings) => {
        if (!cancelled) setName(settings.name);
      })
      .catch(() => {
        if (!cancelled) setName("团队");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [orgId, refreshKey]);

  return { name, loading };
}
