# golden_qa — 知岸入库与检索验收集



> **版本**：v0.4（Plan-RAG R5-1 · 2026-07-06）  

> **用途**：验证结构优先切片元数据（章节 + 页码）与 **hybrid 检索 Hit@3** 自动化。  

> **机器可读 SSOT**：`backend/tests/fixtures/golden_qa.json`



## 测试文档



| 文档 | 路径 | 说明 |

|------|------|------|

| MD 手册 | `backend/tests/fixtures/golden_handbook.md` | GQ-1～3、5～8、11～12 章节结构；GQ-11 含 MD 表格 |

| DOCX 手册 | `backend/tests/fixtures/golden_handbook.docx` | GQ-9 入库→检索（与 AC-8 同源） |

| PDF 页码 | 测试内动态生成 `golden_handbook.pdf`（reportlab） | GQ-4 命中第 2 页 · GQ-10 跨页合并切片（末页页码） |



> **PDF 跨页说明**：测试用小 PDF 两页文本较短，入库时会合并为单 chunk，`page_number` 取**末页**（与 `chunker.py` 合并逻辑一致）。



## 用例（章节 + 页码 + Hit@3）



| ID | 类型 | 问题 | 期望 `section_title` | 期望 `heading_path` 含 | 期望 `page_number` | 期望 content 含 | Hit@3 |

|----|------|------|---------------------|------------------------|-------------------|-----------------|-------|

| GQ-1 | MD | 年假有多少天？ | `1.1 年假` | `考勤制度` | — | `年假10天` | ✅ 自动 |

| GQ-2 | MD | 迟到怎么处理？ | `1.2 迟到` | `考勤制度` | — | `迟到 30 分钟` | ✅ 自动 |

| GQ-3 | MD | 年终奖什么时候发？ | `2.1 年终奖` | `薪酬福利` | — | `12 月` | ✅ 自动 |

| GQ-4 | PDF 跨页 | annual leave 10 days which page | — | — | `2` | `annual leave 10 days` | ✅ 自动 |

| GQ-5 | MD | 每月餐补多少钱？ | `2.2 餐补` | `薪酬福利` | — | `300 元` | ✅ 自动 |

| GQ-6 | MD | 年假需要提前多久申请？ | `1.1 年假` | `考勤制度` | — | `提前两周` | ✅ 自动 |

| GQ-7 | 条款号 | 员工手册 1.2 条款对迟到怎么规定？ | `1.2 迟到` | `考勤制度` | — | `迟到 30 分钟` | ✅ 自动 |

| GQ-8 | 否定问法 | 迟到超过 30 分钟不会按旷工算吧？ | `1.2 迟到` | `考勤制度` | — | `旷工` | ✅ 自动 |

| GQ-9 | DOCX | 年假有多少天？ | `1.1 年假` | `考勤制度` | — | `年假10天` | ✅ 自动 |

| GQ-10 | PDF 跨页 | annual leave apply two weeks in advance | — | — | `2`（小 PDF 合并切片取末页） | `Apply annual leave two weeks` | ✅ 自动 |

| GQ-11 | MD 表格 | 餐补福利表里每月多少钱？ | `2.2 餐补` | `薪酬福利` | — | `300 元/月` | ✅ 自动 |

| GQ-12 | 改写问法 | 带薪年休假可以休多少天？ | `1.1 年假` | `考勤制度` | — | `年假10天` | ✅ 自动 |



> **Hit@3 定义**（TECH-4 §4.3.8）：对每题 hybrid 检索取 Top-3，**至少 1 条** chunk 同时满足上表期望字段即 Pass。  

> 自动化测试（`test_retrieval_golden.py`）从 **`golden_qa.json`** 加载用例，使用**词重叠 mock 嵌入**（CI job **`R5-2 golden Hit@3 gate`** + 本地）；生产环境用通义嵌入 + 同一套 golden 表手跑（EW-C2 / R5-3）。



## 自动化验收



```powershell

cd backend

$env:EMBEDDING_PROVIDER='mock'

py -3.11 -m pytest tests/test_retrieval_golden.py -v

```



全量回归：



```powershell

py -3.11 -m pytest -v

```



## 人工验收（生产嵌入 · EW-C2 / R5-3）



1. 上传真实员工手册 PDF → 问「年假几天」→ 引用含章节 + 页码  

2. `pytest tests/test_ingestion_golden.py tests/test_retrieval_golden.py -v` 全绿  

3. 通义嵌入手跑 Hit@3 并记入 [`RAG_PRODUCTION_BASELINE.md`](RAG_PRODUCTION_BASELINE.md)（EW-C2 ✅ 通义 10/10；R5-1 扩题后须补跑 **12 题**）

