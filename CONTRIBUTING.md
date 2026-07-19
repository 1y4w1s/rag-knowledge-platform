# 睿阁项目约定

## 提交信息格式

```
<type>: <简短描述>

<详细说明（可选）>
```

### 类型

| 前缀 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 |
| `refactor` | 代码重构，不改变功能 |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `docs` | 文档 |
| `chore` | 构建/工具/配置 |
| `ci` | CI 配置 |
| `bench` | 评测/基线 |

### 示例

```
fix: FTS tsquery 过滤 &|!() 特殊字符
feat: 统一评测入口 scripts/run_benchmark.py
bench: Enterprise QA 校准 56%→98%
```

## 分支命名

- `main` — 稳定分支
- `feat/<name>` — 新功能
- `fix/<name>` — 修复
- `bench/<name>` — 评测相关工作

## 代码审查

- 所有 PR 至少 1 人 review 后合并
- 禁止直接 push 到 main
