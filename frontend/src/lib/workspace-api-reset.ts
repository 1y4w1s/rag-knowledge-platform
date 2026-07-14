/** Lets api modules call Context `resetToPersonal` without importing React. */

let resetHandler: (() => void) | null = null;

export function registerWorkspaceApiReset(handler: () => void): void {
  resetHandler = handler;
}

export function triggerWorkspaceApiReset(): void {
  resetHandler?.();
}

export function isWorkspaceForbidden(status: number, detail: string): boolean {
  if (status !== 403) return false;
  return detail.includes("工作区") || detail.toLowerCase().includes("workspace");
}
