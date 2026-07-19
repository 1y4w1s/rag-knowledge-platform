/** ORG-2.5 · PRD ORG-1-3 E6：未分配成员进团队空间的提示条 */
export function UnassignedDepartmentBanner() {
  return (
    <div
      role="status"
      className="alert-banner-ready mb-5 rounded-[10px] border px-4 py-3 text-sm"
    >
      <p className="font-semibold">尚未分配部门</p>
      <p className="mt-0.5 text-[0.8125rem] opacity-90">
        请联系管理员在「组织与部门」中为你指派主部门后，方可创建资料库与开始对话。
      </p>
    </div>
  );
}
