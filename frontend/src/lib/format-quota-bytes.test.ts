import { describe, expect, it } from "vitest";

import {
  formatQuotaBytes,
  shouldShowKbQuotaHint,
} from "@/lib/format-quota-bytes";

describe("formatQuotaBytes", () => {
  it("formats GiB / MiB / KiB / B", () => {
    expect(formatQuotaBytes(10 * 1024 ** 3)).toBe("10.00 GiB");
    expect(formatQuotaBytes(1536 * 1024)).toBe("1.50 MiB");
    expect(formatQuotaBytes(2048)).toBe("2.0 KiB");
    expect(formatQuotaBytes(42)).toBe("42 B");
  });
});

describe("shouldShowKbQuotaHint", () => {
  it("only for writers when quota enabled", () => {
    expect(
      shouldShowKbQuotaHint({
        uploadAllowed: true,
        quotaMaxBytes: 10 * 1024 ** 3,
      }),
    ).toBe(true);
    expect(
      shouldShowKbQuotaHint({
        uploadAllowed: false,
        quotaMaxBytes: 10 * 1024 ** 3,
      }),
    ).toBe(false);
    expect(
      shouldShowKbQuotaHint({ uploadAllowed: true, quotaMaxBytes: 0 }),
    ).toBe(false);
    expect(
      shouldShowKbQuotaHint({ uploadAllowed: true, quotaMaxBytes: null }),
    ).toBe(false);
  });
});
