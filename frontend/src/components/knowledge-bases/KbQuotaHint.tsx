import {
  formatQuotaBytes,
  shouldShowKbQuotaHint,
} from "@/lib/format-quota-bytes";

type KbQuotaHintProps = {
  uploadAllowed: boolean;
  quotaUsedBytes: number | null | undefined;
  quotaMaxBytes: number | null | undefined;
};

export function KbQuotaHint({
  uploadAllowed,
  quotaUsedBytes,
  quotaMaxBytes,
}: KbQuotaHintProps) {
  if (
    !shouldShowKbQuotaHint({ uploadAllowed, quotaMaxBytes }) ||
    quotaUsedBytes == null ||
    quotaMaxBytes == null
  ) {
    return null;
  }

  return (
    <p className="mt-1.5 text-[0.72rem] text-muted" data-testid="kb-quota-hint">
      容量：已用 {formatQuotaBytes(quotaUsedBytes)} / 上限{" "}
      {formatQuotaBytes(quotaMaxBytes)}
      （含回收站与历史版本 · 运营硬闸，非计费）
    </p>
  );
}
