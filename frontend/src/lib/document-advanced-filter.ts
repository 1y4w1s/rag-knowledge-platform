export type DocumentFormatFilter = "pdf" | "docx";

export type DocumentStatusGroup = "processing" | "failed" | "completed";

export interface DocumentListFilters {
  formats: DocumentFormatFilter[];
  statuses: DocumentStatusGroup[];
  uploadedFrom: string | null;
  uploadedTo: string | null;
}

const FORMAT_VALUES = new Set<DocumentFormatFilter>(["pdf", "docx"]);
const STATUS_VALUES = new Set<DocumentStatusGroup>([
  "processing",
  "failed",
  "completed",
]);

export const DOCUMENT_FORMAT_OPTIONS: {
  value: DocumentFormatFilter;
  label: string;
}[] = [
  { value: "pdf", label: "PDF" },
  { value: "docx", label: "DOCX" },
];

export const DOCUMENT_STATUS_OPTIONS: {
  value: DocumentStatusGroup;
  label: string;
}[] = [
  { value: "processing", label: "整理中" },
  { value: "failed", label: "失败" },
  { value: "completed", label: "已完成" },
];

function asStringArray<T extends string>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function parseFormats(params: URLSearchParams): DocumentFormatFilter[] {
  const values = [
    ...params.getAll("file_type"),
    ...(params.get("file_type")?.split(",") ?? []),
  ];
  const formats: DocumentFormatFilter[] = [];
  for (const raw of values) {
    const token = raw.trim().toLowerCase();
    if (FORMAT_VALUES.has(token as DocumentFormatFilter)) {
      formats.push(token as DocumentFormatFilter);
    }
  }
  return [...new Set(formats)];
}

function parseStatuses(params: URLSearchParams): DocumentStatusGroup[] {
  const values = [
    ...params.getAll("status"),
    ...(params.get("status")?.split(",") ?? []),
  ];
  const statuses: DocumentStatusGroup[] = [];
  for (const raw of values) {
    const token = raw.trim().toLowerCase();
    if (STATUS_VALUES.has(token as DocumentStatusGroup)) {
      statuses.push(token as DocumentStatusGroup);
    }
  }
  return [...new Set(statuses)];
}

function parseDateParam(value: string | null): string | null {
  if (!value) return null;
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
}

export function parseDocumentListFilters(search: string): DocumentListFilters {
  const params = new URLSearchParams(search);
  return {
    formats: parseFormats(params),
    statuses: parseStatuses(params),
    uploadedFrom: parseDateParam(params.get("uploaded_from")),
    uploadedTo: parseDateParam(params.get("uploaded_to")),
  };
}

export function normalizeDocumentListFilters(
  filters: Partial<DocumentListFilters> | null | undefined,
): DocumentListFilters {
  return {
    formats: asStringArray<DocumentFormatFilter>(filters?.formats),
    statuses: asStringArray<DocumentStatusGroup>(filters?.statuses),
    uploadedFrom: filters?.uploadedFrom ?? null,
    uploadedTo: filters?.uploadedTo ?? null,
  };
}

export function hasActiveListFilters(filters: DocumentListFilters): boolean {
  const safe = normalizeDocumentListFilters(filters);
  return (
    safe.formats.length > 0 ||
    safe.statuses.length > 0 ||
    safe.uploadedFrom !== null ||
    safe.uploadedTo !== null
  );
}

export function buildUrlWithDocumentListFilters(
  pathname: string,
  search: string,
  filters: DocumentListFilters,
): string {
  const safe = normalizeDocumentListFilters(filters);
  const params = new URLSearchParams(search);
  params.delete("file_type");
  params.delete("status");
  params.delete("uploaded_from");
  params.delete("uploaded_to");

  for (const format of safe.formats) {
    params.append("file_type", format);
  }
  for (const status of safe.statuses) {
    params.append("status", status);
  }
  if (safe.uploadedFrom) {
    params.set("uploaded_from", safe.uploadedFrom);
  }
  if (safe.uploadedTo) {
    params.set("uploaded_to", safe.uploadedTo);
  }

  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function buildUrlWithoutListFilters(
  pathname: string,
  search: string,
): string {
  const params = new URLSearchParams(search);
  params.delete("file_type");
  params.delete("status");
  params.delete("uploaded_from");
  params.delete("uploaded_to");
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export interface DocumentListApiFilters {
  file_type?: string[];
  status?: string[];
  uploaded_from?: string;
  uploaded_to?: string;
}

export function toDocumentListApiFilters(
  filters: DocumentListFilters,
): DocumentListApiFilters {
  const safe = normalizeDocumentListFilters(filters);
  const api: DocumentListApiFilters = {};
  if (safe.formats.length > 0) {
    api.file_type = [...safe.formats];
  }
  if (safe.statuses.length > 0) {
    api.status = [...safe.statuses];
  }
  if (safe.uploadedFrom) {
    api.uploaded_from = safe.uploadedFrom;
  }
  if (safe.uploadedTo) {
    api.uploaded_to = safe.uploadedTo;
  }
  return api;
}

export function describeActiveListFilters(
  filters: DocumentListFilters,
): string[] {
  const safe = normalizeDocumentListFilters(filters);
  const parts: string[] = [];
  if (safe.formats.length > 0) {
    parts.push(
      `格式 ${safe.formats.map((f) => f.toUpperCase()).join("、")}`,
    );
  }
  if (safe.statuses.length > 0) {
    const labels = safe.statuses.map(
      (status) =>
        DOCUMENT_STATUS_OPTIONS.find((opt) => opt.value === status)?.label ??
        status,
    );
    parts.push(`状态 ${labels.join("、")}`);
  }
  if (safe.uploadedFrom || safe.uploadedTo) {
    if (safe.uploadedFrom && safe.uploadedTo) {
      parts.push(`上传 ${safe.uploadedFrom} 至 ${safe.uploadedTo}`);
    } else if (safe.uploadedFrom) {
      parts.push(`上传自 ${safe.uploadedFrom}`);
    } else {
      parts.push(`上传至 ${safe.uploadedTo}`);
    }
  }
  return parts;
}
