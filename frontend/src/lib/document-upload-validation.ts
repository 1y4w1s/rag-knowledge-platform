/** 上传前校验：空文件、同批/库内重名（与后端 upload.py 口径一致） */

function normalizeFilename(name: string): string {
  const base = name.split(/[/\\]/).pop() ?? name;
  return base.trim();
}

function duplicateNames(names: string[]): string[] {
  const seen = new Set<string>();
  const dupes = new Set<string>();
  for (const name of names) {
    const key = normalizeFilename(name).toLowerCase();
    if (!key) continue;
    if (seen.has(key)) dupes.add(normalizeFilename(name));
    seen.add(key);
  }
  return [...dupes];
}

export function validateUploadFiles(
  files: File[],
  existingFilenames: string[] = [],
): { ok: true; files: File[] } | { ok: false; message: string } {
  if (files.length === 0) {
    return { ok: false, message: "请至少选择一个文件" };
  }

  const emptyNames = files
    .filter((file) => file.size === 0)
    .map((file) => normalizeFilename(file.name));

  if (emptyNames.length > 0) {
    return {
      ok: false,
      message: `以下文件为空（0 字节），请添加内容后再上传：${emptyNames.join("、")}`,
    };
  }

  const batchDupes = duplicateNames(files.map((file) => file.name));
  if (batchDupes.length > 0) {
    return {
      ok: false,
      message: `本次选择了重复文件名，请去掉重复项：${batchDupes.join("、")}`,
    };
  }

  const existingKeys = new Set(
    existingFilenames.map((name) => normalizeFilename(name).toLowerCase()),
  );
  const conflicts = files
    .map((file) => normalizeFilename(file.name))
    .filter((name) => existingKeys.has(name.toLowerCase()));

  if (conflicts.length > 0) {
    return {
      ok: false,
      message: `资料库中已存在同名文件：${[...new Set(conflicts)].join("、")}`,
    };
  }

  return { ok: true, files };
}
