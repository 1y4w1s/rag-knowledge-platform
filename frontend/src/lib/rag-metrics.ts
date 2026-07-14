/** Dashboard RAG 指标展示（EW-C3 · 来自 GET /dashboard/stats） */
export interface RagMetricsDisplay {
  totalChunks: number;
  goldenHitRatePercent: number | null;
  goldenBaselineEvaluatedAt: string | null;
  avgRetrievalLatencyMs: number | null;
  retrievalLatencySampleCount: number;
}

export function ragMetricsFromStats(stats: {
  total_chunk_count: number;
  golden_hit_rate_percent: number | null;
  golden_baseline_evaluated_at: string | null;
  avg_retrieval_latency_ms: number | null;
  retrieval_latency_sample_count: number;
}): RagMetricsDisplay {
  return {
    totalChunks: stats.total_chunk_count,
    goldenHitRatePercent: stats.golden_hit_rate_percent,
    goldenBaselineEvaluatedAt: stats.golden_baseline_evaluated_at,
    avgRetrievalLatencyMs: stats.avg_retrieval_latency_ms,
    retrievalLatencySampleCount: stats.retrieval_latency_sample_count,
  };
}
