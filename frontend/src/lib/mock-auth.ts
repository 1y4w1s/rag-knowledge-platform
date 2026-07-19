/** Wave 4.1 demo KB routes — replace with real IDs in Wave 4.4+. */
export const DEMO_KB_ID = "demo-kb";
export const DEMO_DOC_ID = "demo-doc";

/** Wave 4.2 demo login — 与 backend/scripts/seed_enterprise_demo.py 一致 */
export const DEMO_CREDENTIALS = {
  email: "demo-admin@example.com",
  username: "demo_admin",
  password: "password123",
  orgName: "睿阁演示公司",
  nickname: "演示管理员",
} as const;

export const DEMO_MEMBER_CREDENTIALS = {
  email: "demo-member@example.com",
  username: "demo_member",
  password: "password123",
  nickname: "演示成员",
} as const;
