/** NW-25 I-2 · 容量展示（与后端 _format_bytes 口径对齐）。 */
export function formatQuotaBytes(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GiB`;
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(2)} MiB`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} KiB`;
  return `${n} B`;
}

export function shouldShowKbQuotaHint(opts: {
  uploadAllowed: boolean;
  quotaMaxBytes: number | null | undefined;
}): boolean {
  return (
    opts.uploadAllowed &&
    opts.quotaMaxBytes != null &&
    opts.quotaMaxBytes > 0
  );
}
