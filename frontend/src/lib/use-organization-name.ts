import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import { fetchOrganizationSettings } from "@/lib/organization-api";

/** Fetches org display name for sidebar (H4 · W2). Cached per mount / org_id change. */
export function useOrganizationName(): { name: string; loading: boolean } {
  const { user } = useAuth();
  const orgId = user?.org_id ?? null;
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

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
  }, [orgId]);

  return { name, loading };
}
