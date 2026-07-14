import { useCallback, useEffect, useState } from "react";

import { SettingsFormCard } from "@/components/settings/SettingsFormCard";
import { Button } from "@/components/ui/button";
import {
  createApiKey,
  deleteApiKey,
  listApiKeys,
  type ApiKeyCreateResponse,
  type ApiKeyItem,
} from "@/lib/settings-api";

export function ApiKeyManager() {
  const [keys, setKeys] = useState<ApiKeyItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<ApiKeyCreateResponse | null>(null);
  const [keyName, setKeyName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

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

  async function handleCreate() {
    const name = keyName.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      const result = await createApiKey(name);
      setNewKey(result);
      setKeyName("");
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
    <div id="account-api-keys" className="mt-10">
      <SettingsFormCard title="API Key 管理">
        <p className="text-sm text-foreground-secondary">
          API Key 可用于外部脚本和系统直接调通知岸 API，无需登录。创建后请立即复制，密钥仅显示一次。
        </p>

        {error ? (
          <p className="mt-2 text-sm text-red-600">{error}</p>
        ) : null}

        {/* 创建表单 */}
        <div className="mt-4 flex items-end gap-2">
          <div className="flex-1">
            <label htmlFor="api-key-name" className="mb-1 block text-xs font-medium text-foreground-secondary">
              名称
            </label>
            <input
              id="api-key-name"
              type="text"
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              placeholder="例如：CI/CD 部署脚本"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-foreground"
              onKeyDown={(e) => { if (e.key === "Enter") void handleCreate(); }}
            />
          </div>
          <Button
            type="button"
            variant="brand"
            size="sm"
            disabled={creating || !keyName.trim()}
            onClick={() => void handleCreate()}
          >
            {creating ? "创建中…" : "创建 Key"}
          </Button>
        </div>

        {/* 新 Key 展示（仅一次） */}
        {newKey ? (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-800">新 API Key 已创建（仅显示一次，请立即复制）</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap rounded bg-white px-2 py-1 text-sm font-mono">
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

        {/* Key 列表 */}
        <div className="mt-4 space-y-2">
          {loading ? (
            <p className="text-sm text-foreground-secondary">加载中…</p>
          ) : keys.length === 0 ? (
            <p className="text-sm text-foreground-secondary">暂无 API Key</p>
          ) : (
            keys.map((key) => (
              <div
                key={key.id}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{key.name}</span>
                    <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono text-muted-foreground">
                      {key.prefix}…
                    </code>
                    {!key.is_active ? (
                      <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs text-red-700">
                        已撤销
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-0.5 text-xs text-foreground-secondary">
                    创建于 {new Date(key.created_at).toLocaleDateString("zh-CN")}
                    {key.last_used_at
                      ? ` · 上次使用 ${new Date(key.last_used_at).toLocaleDateString("zh-CN")}`
                      : " · 尚未使用"}
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
      </SettingsFormCard>
    </div>
  );
}
