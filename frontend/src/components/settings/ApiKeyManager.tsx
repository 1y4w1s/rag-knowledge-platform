import { useCallback, useEffect, useState } from "react";

import { SettingsFormCard } from "@/components/settings/SettingsFormCard";
import { Button } from "@/components/ui/button";
import {
  createApiKey,
  deleteApiKey,
  fetchAccountSettings,
  listApiKeys,
  type ApiKeyCreateResponse,
  type ApiKeyItem,
  type AccountSettings,
} from "@/lib/settings-api";

const DEFAULT_EXPIRY_DAYS = 90;

function todayLocalDate(): string {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

function defaultExpiryDate(): string {
  const d = new Date(Date.now() + DEFAULT_EXPIRY_DAYS * 24 * 60 * 60 * 1000);
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

/** 日期选择值（本地）→ 当日 23:59:59 的 UTC ISO，交给后端落库。 */
function toEndOfDayIso(dateValue: string): string {
  const [y, m, d] = dateValue.split("-").map(Number);
  return new Date(y, m - 1, d, 23, 59, 59, 999).toISOString();
}

function formatExpiry(iso: string | null): string {
  if (!iso) return "永久有效";
  return `有效期至 ${new Date(iso).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })}`;
}

export function ApiKeyManager() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [account, setAccount] = useState<AccountSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<ApiKeyCreateResponse | null>(null);
  const [keyName, setKeyName] = useState("");
  const [expiryDate, setExpiryDate] = useState(defaultExpiryDate());
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const canCreate =
    account?.account_type === "enterprise" && account?.org_role === "admin";

  const loadKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setKeys(await listApiKeys());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadKeys();
  }, [loadKeys]);

  useEffect(() => {
    void fetchAccountSettings()
      .then(setAccount)
      .catch(() => setAccount(null));
  }, []);

  async function handleCreate() {
    const name = keyName.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      const result = await createApiKey(
        name,
        expiryDate ? toEndOfDayIso(expiryDate) : null,
      );
      setNewKey(result);
      setKeyName("");
      setExpiryDate(defaultExpiryDate());
      await loadKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(keyId: string) {
    if (!confirm("确定撤销此 API Key？撤销后使用该 Key 的请求将立即失效。")) return;
    setError(null);
    try {
      await deleteApiKey(keyId);
      await loadKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "撤销失败");
    }
  }

  async function handleCopy(rawKey: string) {
    try {
      await navigator.clipboard.writeText(rawKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
      const ta = document.createElement("textarea");
      ta.value = rawKey;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div id="account-api-keys">
      <SettingsFormCard title="API Key">
        <details className="settings-api-details">
          <summary>管理密钥</summary>
          <div className="mt-3">
        {error ? (
          <p className="mt-2 text-sm text-red-600">{error}</p>
        ) : null}

        {canCreate ? (
          <div className="mt-3">
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              API Key 等同账号密码，拥有账号全部权限；请妥善保管，泄露视为账号泄露。
            </div>
            <div className="mt-2 flex items-end gap-2">
              <div className="flex-1">
                <label htmlFor="api-key-name" className="settings-field-label">
                  名称
                </label>
                <input
                  id="api-key-name"
                  type="text"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  placeholder="名称"
                  className="settings-field-input"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void handleCreate();
                  }}
                />
              </div>
              <div className="flex-1">
                <label htmlFor="api-key-expiry" className="settings-field-label">
                  有效期
                </label>
                <input
                  id="api-key-expiry"
                  type="date"
                  value={expiryDate}
                  min={todayLocalDate()}
                  onChange={(e) => setExpiryDate(e.target.value)}
                  className="settings-field-input"
                />
              </div>
              <Button
                type="button"
                variant="brand"
                size="sm"
                disabled={creating || !keyName.trim()}
                onClick={() => void handleCreate()}
              >
                {creating ? "创建中…" : "创建"}
              </Button>
            </div>
            <p className="mt-1 text-xs text-muted">
              默认建议 {DEFAULT_EXPIRY_DAYS} 天；清空后为永久有效。
            </p>
          </div>
        ) : (
          <p className="mt-2 text-xs text-muted">
            仅团队管理员或所有者可创建 API Key。
          </p>
        )}

        {newKey ? (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-800">
              新密钥仅显示一次
            </p>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap rounded bg-white px-2 py-1 font-mono text-sm">
                {newKey.raw_key}
              </code>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void handleCopy(newKey.raw_key)}
              >
                {copied ? "已复制" : "复制"}
              </Button>
            </div>
            <button
              type="button"
              className="mt-1 text-xs text-amber-600 underline"
              onClick={() => setNewKey(null)}
            >
              关闭
            </button>
          </div>
        ) : null}

        <div className="mt-4 space-y-2">
          {loading ? (
            <p className="text-sm text-muted">加载中…</p>
          ) : keys.length === 0 ? (
            <p className="text-sm text-muted">暂无 API Key</p>
          ) : (
            keys.map((key) => (
              <div
                key={key.id}
                className="flex items-center justify-between rounded-md border border-[var(--line2)] px-3 py-2"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{key.name}</span>
                    <code className="rounded bg-[var(--surf2)] px-1.5 py-0.5 font-mono text-xs text-muted">
                      {key.prefix}…
                    </code>
                    <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-800">
                      全权
                    </span>
                    {!key.is_active ? (
                      <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs text-red-700">
                        已撤销
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-0.5 text-xs text-muted">
                    创建于 {new Date(key.created_at).toLocaleDateString("zh-CN")}
                    {key.last_used_at
                      ? ` · 上次使用 ${new Date(key.last_used_at).toLocaleDateString("zh-CN")}`
                      : " · 尚未使用"}
                    {` · ${formatExpiry(key.expires_at)}`}
                  </p>
                </div>
                {key.is_active ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="ml-2 text-red-600 hover:bg-red-50"
                    onClick={() => void handleDelete(key.id)}
                  >
                    撤销
                  </Button>
                ) : null}
              </div>
            ))
          )}
        </div>
          </div>
        </details>
      </SettingsFormCard>
    </div>
  );
}
