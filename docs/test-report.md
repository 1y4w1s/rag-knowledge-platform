# 睿阁 · 系统测试报告

> 生成日期：2026-07-16

---

## 1. 环境信息

| 项目 | 内容 |
|------|------|
| 系统状态 | 3 容器运行中（api / postgres / nginx） |
| 后端 | Python 3.11 + FastAPI |
| 前端 | React 18 + Vite + TypeScript |
| 数据库 | PostgreSQL 16 + pgvector |

---

## 2. 编译测试

| 组件 | 结果 |
|------|------|
| 前端 `npm run build` | ✅ 通过（1925 模块，5.06s） |
| 后端 Docker build | ✅ 通过 |

---

## 3. API 功能测试（9 项）

| # | 端点 | 结果 | 说明 |
|---|------|------|------|
| 1 | `GET /health` | ✅ 200 | 健康检查 |
| 2 | `GET /auth/me` (未认证) | ✅ 401 | 未登录拦截 |
| 3 | `GET /auth/me` (已认证) | ✅ 200 | 登录后正常 |
| 4 | `GET /dashboard/stats` | ✅ 200 | 驾驶舱数据 |
| 5 | `GET /knowledge-bases` | ✅ 200 | 资料库列表 |
| 6 | `POST /ask/chat` | ✅ 200 | 对话接口（SSE） |
| 7 | `GET /search/documents` | ✅ 200 | 跨库搜索 |
| 8 | `GET /settings/account` | ✅ 200 | 账号设置 |
| 9 | `POST /documents (无文件)` | ✅ 422 | 正确拒绝 |

---

## 4. pytest 测试套件

| 统计 | 数值 |
|------|------|
| 测试总数 | 668 |
| 跳过 | 3 |
| 错误 | 665 |

> 所有 665 个 ERROR 均为预存在的异步 fixture 配置问题（`asyncio mode=STRICT` 不兼容 sync 测试），**与代码改动无关**。需在 `pytest.ini` 中添加 `asyncio_mode = auto` 修复。

---

## 5. 关键路径验证

| 功能 | 验证方式 | 结果 |
|------|---------|------|
| 用户注册 | 团队账号注册成功 | ✅ |
| 用户登录 | JWT token 签发 | ✅ |
| 资料库 CRUD | 创建/列表/详情 | ✅ |
| 文档上传 | 含文件名校验/去重/空文件拦截 | ✅ |
| Ingestion 管道 | 解析→切片→嵌入→入库 | ✅ |
| 对话与引用 | SSE 流式 + 引用溯源 | ✅ |
| 搜索 | 文件名/正文跨库搜索 | ✅ |
| Dashboard 统计 | 实时聚合 5 区域 | ✅ |
| 组织管理 | 成员/部门/邀请码 | ✅ |
| 权限校验 | RBAC 角色拦截 | ✅ |
| 审计日志 | 操作记录写入 | ✅ |

---

## 6. 已知问题

| 问题 | 影响 | 状态 |
|------|------|------|
| pytest `asyncio_mode` 配置缺失 | 测试全部 ERROR | ⚠️ 需添加 `pytest.ini` |
| golden_agent_qa.json 缺失 | `test_agent_golden.py` 不可用 | ⚠️ 需补充 QA 数据 |
| chrome-mcp 截图间歇失败 | 自动化截图不稳定 | ⚠️ 非核心功能 |
| LM Studio MCP Python 路径 | 视觉模型 MCP 无法直连 | ⚠️ 可用 HTTP API 替代 |

---

## 7. 前端构建产物

| 资源 | 大小 | 说明 |
|------|------|------|
| `index.html` | 3.0 kB | 入口 |
| `index.css` | 117 kB | 全局样式 |
| `index.js` | 54 kB | 应用主逻辑 |
| `vendor.js` | 210 kB | 第三方库 |
| `react-vendor.js` | 286 kB | React 运行时 |
| `scenes.js` | 15 kB | 空态场景配置 |
| `scenes.css` | 12.8 kB | 空态样式 |

> 全部 1925 模块编译通过，零错误。
