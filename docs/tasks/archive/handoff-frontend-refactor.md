# 知岸 — 新窗交接：前端重构 G～M

## 当前状态

**Eval-Ops P0/P1 全部关单。Format-F (F1 xlsx + F2 pptx + F3 PDF表) 全部完成。性能索引 (migration 026) 已加，M2 列表 p95=47ms 达标。**

## 下一项任务

按 `docs/tasks/code-refactor-spec.md` 顺序，**P2 前端舟山** 是下一个：

```
P2 前端舟山 —— 每条一窗
  ├─ G. AskPage + ChatPage 提取共享组件
  ├─ H. use-thread-session.ts 拆分为 3 个子 hook
  ├─ I. use-ask-session + use-chat-session 合并
  ├─ J. 28-prop 钻取 → 传对象
  ├─ K. chat-api.ts Zod 运行时校验
  ├─ L. EmptyStateV44.tsx 文件拆分
  └─ M. scenes.tsx 工厂化
```

WIP=1，一次一条，每条一个新对话。

## 最近改动（Format-F）

| 文件 | 改动 |
|------|------|
| `backend/requirements.txt` | 加 `openpyxl>=3.1.2,<4` + `python-pptx>=1.0.0,<2` |
| `backend/app/services/ingestion/parser.py` | 新增 `parse_xlsx()` + `parse_pptx()` + 分支注册 |
| `backend/app/services/ingestion/parser_pdf.py` | 新增 `_parse_pdf_tables_only()` + 集成到 `parse_pdf()` |
| `backend/app/services/documents/upload.py` | `ALLOWED_EXTENSIONS` 加 `.xlsx` `.pptx` |
| `backend/app/services/documents/filters.py` | `ALLOWED_FILE_TYPES` 加 `xlsx` `pptx` |
| `backend/app/services/documents/preview.py` | `_CONTENT_TYPES` 加 xlsx/pptx MIME |
| `frontend/src/lib/document-advanced-filter.ts` | 格式选项加 XLSX + PPTX |
| `backend/alembic/versions/026_performance_indexes.py` | 3 个性能索引 |
| `docs/tasks/format-f1-f2-f3-plan.md` | 子计划文档 |
| `tests/test_xlsx_ingestion.py` | 🔥 新增 |
| `tests/test_pptx_ingestion.py` | 🔥 新增 |
| `tests/test_pdf_table_ingestion.py` | 🔥 新增 |
| `tests/test_m1_smoke.py` | 🔥 新增 |

## 文档同步已做

- PRD.md §6 → 更新为 8 格式表格
- TECH.md §4.2 / §4.3.3 → 新增 xlsx/pptx/PDF表
- enterprise-master-plan.md §6 → F1/F2/F3 标 ✅
- code-refactor-spec.md → F2/F3 标 ✅

## 架构要点（前端重构前必读）

1. **先 plan 再动**：每条任务先输出 `docs/tasks/code-refactor-{代号}-plan.md`，你审过再 implement
2. **npm run build 必须绿**：前端改动后必须 build 通过
3. **不改业务行为**：纯重构，不修 bug、不调样式、不改 API
4. **WIP=1**：一个对话只做一个原子任务

## 技术栈

- React + TypeScript + Vite（前端）
- FastAPI + PostgreSQL/pgvector（后端）
- Docker Compose 部署
