import { describe, expect, it } from "vitest";

import type { StoredUser } from "@/lib/auth-storage";
import type { OrgUnit } from "@/lib/org-units-api";
import {
  canManageOwnUnitMembers,
  filterManagedUnitOptions,
} from "@/lib/org-permissions";

function user(partial: Partial<StoredUser>): StoredUser {
  return {
    id: "u1",
    email: "a@example.com",
    username: "a",
    nickname: null,
    account_type: "enterprise",
    org_id: "o1",
    org_role: "member",
    is_owner: false,
    primary_unit_id: null,
    unit_ids: [],
    unit_admin_unit_ids: [],
    ...partial,
  };
}

function unit(id: string, name: string): OrgUnit {
  return {
    id,
    org_id: "o1",
    parent_id: null,
    name,
    depth: 0,
    child_count: 0,
    member_count: 0,
    kb_count: 0,
    created_at: "2026-01-01T00:00:00Z",
  };
}

describe("canManageOwnUnitMembers", () => {
  it("unit_admin（非公司 Admin）可见入口", () => {
    expect(
      canManageOwnUnitMembers(
        user({ unit_admin_unit_ids: ["dept-a"] }),
      ),
    ).toBe(true);
  });

  it("公司 Admin / Owner 不可见（走组织与部门）", () => {
    expect(
      canManageOwnUnitMembers(
        user({
          org_role: "admin",
          unit_admin_unit_ids: ["dept-a"],
        }),
      ),
    ).toBe(false);
    expect(
      canManageOwnUnitMembers(
        user({
          is_owner: true,
          org_role: "admin",
          unit_admin_unit_ids: ["dept-a"],
        }),
      ),
    ).toBe(false);
  });

  it("纯 Member / 个人版不可见", () => {
    expect(canManageOwnUnitMembers(user({}))).toBe(false);
    expect(
      canManageOwnUnitMembers(
        user({ account_type: "personal", org_id: null, org_role: null }),
      ),
    ).toBe(false);
    expect(canManageOwnUnitMembers(null)).toBe(false);
  });
});

describe("filterManagedUnitOptions", () => {
  it("仅保留托管节点，排除路径上的祖先", () => {
    const units = [
      unit("root", "公司"),
      unit("dept-a", "市场部"),
      unit("dept-b", "研发部"),
    ];
    expect(
      filterManagedUnitOptions(units, ["dept-a"]).map((u) => u.id),
    ).toEqual(["dept-a"]);
  });

  it("空托管列表 → 空选项", () => {
    expect(filterManagedUnitOptions([unit("a", "A")], [])).toEqual([]);
    expect(filterManagedUnitOptions([unit("a", "A")], null)).toEqual([]);
  });
});
