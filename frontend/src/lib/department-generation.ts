/** Options for discarding in-flight API responses after department switches (ORG-1-2 §2.3). */
export interface DepartmentGenerationOptions {
  expectedGen: number;
  getCurrentGeneration: () => number;
}

/** True when a newer `setDepartment` / align reset bumped generation. */
export function isStaleDepartmentGeneration(
  options: DepartmentGenerationOptions | undefined,
): boolean {
  if (!options) return false;
  return options.getCurrentGeneration() !== options.expectedGen;
}

/** Combined workspace + department generation check (ORG-1-6 §5.3 · ORG-3.3 fetch 层用). */
export interface ScopeGenerationOptions {
  expectedWorkspaceGen: number;
  getCurrentWorkspaceGeneration: () => number;
  expectedDepartmentGen: number;
  getCurrentDepartmentGeneration: () => number;
}

export function isStaleScopeGeneration(
  options: ScopeGenerationOptions | undefined,
): boolean {
  if (!options) return false;
  return (
    options.getCurrentWorkspaceGeneration() !== options.expectedWorkspaceGen ||
    options.getCurrentDepartmentGeneration() !== options.expectedDepartmentGen
  );
}
