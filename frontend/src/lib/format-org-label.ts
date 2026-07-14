/** WS-2-1 §1.1.2 · 策略 C — 侧栏短标签（与 preview-sidebar-ws2-1 同源） */

const ORG_PREFIXES = ["中华人民共和国", "中国"] as const;

const ORG_SUFFIXES = [
  "有限责任公司",
  "股份有限公司",
  "有限公司",
] as const;

const BRAND_ANCHOR_RE = /(集团|股份|公司|中心|研究院|工作室|分公司)/;

function codePoints(str: string): string[] {
  return Array.from(str);
}

function stripBoilerplate(raw: string): string {
  let s = raw;
  let changed = true;
  while (changed) {
    changed = false;
    for (const prefix of ORG_PREFIXES) {
      if (s.startsWith(prefix)) {
        s = s.slice(prefix.length);
        changed = true;
      }
    }
    for (const suffix of ORG_SUFFIXES) {
      if (s.length >= suffix.length && s.endsWith(suffix)) {
        s = s.slice(0, -suffix.length);
        changed = true;
      }
    }
  }
  return s.trim();
}

function anchorIndexC3a(core: string): number | null {
  const match = core.search(BRAND_ANCHOR_RE);
  if (match > 2) {
    return Math.floor(codePoints(core.slice(0, match)).length / 2);
  }
  return null;
}

function middleWindowLabel(core: string): string {
  const chars = codePoints(core);
  if (chars.length <= 18) return core;
  let mid = anchorIndexC3a(core);
  if (mid === null) mid = Math.floor(chars.length / 2);
  const start = Math.max(0, mid - 7);
  const end = Math.min(chars.length, mid + 7);
  return `…${chars.slice(start, end).join("")}…`;
}

/**
 * Format organization display name for sidebar segmented control.
 * @param name Raw org name from API (up to 255 chars).
 */
export function formatOrgLabel(name: string): string {
  const raw = (name || "").trim().replace(/\s+/g, " ");
  if (!raw) return "…";
  let core = stripBoilerplate(raw);
  if (!core) core = raw;
  return middleWindowLabel(core);
}
