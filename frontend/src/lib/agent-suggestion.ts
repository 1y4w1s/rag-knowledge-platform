/** Agent 模式智能推荐（物尽其用 Phase 3a）。 */

const COMPLEX_PATTERNS = [
  /对比|比较|差异|区别|versus|vs/i,
  /分别|各是多少|各有什么/i,
  /如何计算|怎么算|计算公式/i,
  /以及|并且|还是|或者/i,
  /清单|检查|合规|满足.*要求/i,
  /总结|归纳|汇总|概括/i,
];

/**
 * 判断问句是否适合使用 thorough（精准）模式。
 * 条件：包含复杂关键词 + 长度 > 20 字符。
 */
export function suggestThoroughMode(query: string): boolean {
  const trimmed = query.trim();
  if (trimmed.length < 20) return false;
  return COMPLEX_PATTERNS.some((p) => p.test(trimmed));
}
