# 睿阁前端

React + Vite + shadcn/ui，9 个主路由 + 全局侧栏。

**当前阶段**：Wave 4.3 ✅ Dashboard 统计卡片 · Wave 4.4 知识库 UI。

## 开发

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173

- 默认进入 `/dashboard`
- 登录页 `/login`（无侧栏）
- Mock 角色：`src/lib/mock-auth.ts` 中 `MOCK_USER.role`（`admin` 可见成员/组织 nav）

## 目录

```
frontend/src/
├── components/layout/   # AppSidebar、AppShellLayout
├── components/ui/       # shadcn Button 等
├── pages/               # 9 路由页面
├── routes/              # React Router
└── lib/mock-auth.ts     # Wave 4.1 mock 角色
```

视觉 token 见 `docs/DESIGN.md` DESIGN-2；预览见 `DESIGN.md`。
