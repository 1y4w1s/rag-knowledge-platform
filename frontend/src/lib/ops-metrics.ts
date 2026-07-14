/** Dashboard 运营指标展示（Plan-3E-6b / ORG-3.5 · 来自 GET /dashboard/stats） */
export interface OpsMetricsDisplay {
  ingestionSuccessRate: number | null;
  documentRetryCount7d: number;
  storageCleanupFailureCount: number;
}

export function opsMetricsFromStats(stats: {
  ingestion_success_rate: number | null;
  document_retry_count_7d: number;
  storage_cleanup_failure_count: number;
}): OpsMetricsDisplay {
  return {
    ingestionSuccessRate: stats.ingestion_success_rate,
    documentRetryCount7d: stats.document_retry_count_7d,
    storageCleanupFailureCount: stats.storage_cleanup_failure_count,
  };
}
