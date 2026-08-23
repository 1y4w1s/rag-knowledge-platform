"""配置接线契约测试（masterplan 主题 C · C2）。

背景：Settings（pydantic-settings）应是配置唯一来源。历史缺陷：
1. 死配置——字段声明了但业务代码从未引用（T3-C1~C10、P1-33）；
2. env 直读——业务代码绕过 settings 直接 os.getenv（C-4/P1-33）。

本测试纯 AST 静态扫描（无 import、无 mock、秒级）：
- 遍历 Settings 全部字段，确认每个字段至少被 app/（业务）或 scripts/（运维）引用一处；
- 收集 app/ 下 os.getenv / os.environ 访问点，断言「位置 + 键」都在 C1 §2.4 白名单内。

白名单来源：docs/tasks/audit-c1-config-cleanup.md §2.4
"""

from __future__ import annotations

import ast
import pathlib
from typing import Iterable


BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"
SCRIPTS_ROOT = BACKEND_ROOT / "scripts"
CONFIG_PATH = APP_ROOT / "core" / "config.py"

# C1 §2.4 白名单：(app 相对路径, env 键)。settings 均为优先源，env 仅为兼容回退。
ENV_WHITELIST = {
    ("app/core/redis.py", "CELERY_BROKER_URL"),
    ("app/services/agent/tools/web_search.py", "SEARCH_API_KEY"),
    ("app/services/auth/api_rate_limit.py", "RAG_RATE_LIMIT_MODE"),
    ("app/services/auth/rate_limit_store.py", "RATE_LIMIT_BACKEND"),
    ("app/services/rag/hyde.py", "HYDE_ENABLED"),
    ("app/eval/adversarial_capability/p4_local_env.py", "DATABASE_URL"),
}


def _read_py(path: pathlib.Path) -> str:
    """BOM / CP936 兼容读取：优先 UTF-8-SIG，失败回退 GBK。"""
    for encoding in ("utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _parse(path: pathlib.Path) -> ast.Module | None:
    try:
        return ast.parse(_read_py(path))
    except SyntaxError:
        return None


def _rel(path: pathlib.Path) -> str:
    return path.relative_to(BACKEND_ROOT).as_posix()


def _settings_fields() -> list[str]:
    """从 config.py 提取 Settings 类声明的全部字段名（AnnAssign）。"""
    tree = _parse(CONFIG_PATH)
    assert tree is not None, f"config.py 解析失败: {CONFIG_PATH}"
    fields: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                    and isinstance(stmt.annotation, ast.Name)
                    and stmt.annotation.id != "ClassVar"
                ):
                    fields.append(stmt.target.id)
    return fields


def _iter_py(root: pathlib.Path) -> Iterable[pathlib.Path]:
    if root.is_dir():
        yield from root.rglob("*.py")
    elif root.is_file():
        yield root


def _collect_field_refs(fields: list[str]) -> dict[str, list[tuple[str, int]]]:
    """扫描 app/ + scripts/ 下 settings.<field> 属性访问（排除 config.py 自身）。"""
    refs: dict[str, list[tuple[str, int]]] = {f: [] for f in fields}
    for py in list(_iter_py(APP_ROOT)) + list(_iter_py(SCRIPTS_ROOT)):
        if py.resolve() == CONFIG_PATH.resolve():
            continue
        tree = _parse(py)
        if tree is None:
            # 解析失败的文件退化为字符串匹配，避免漏检真实引用
            text = _read_py(py)
            for field in fields:
                if f"settings.{field}" in text:
                    refs[field].append((_rel(py), 0))
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "settings"
                and node.attr in refs
            ):
                refs[node.attr].append((_rel(py), node.lineno))
    return refs


def _env_access_points() -> list[tuple[str, int, str]]:
    """收集 app/ 下 os.getenv / os.environ.get / os.environ[...] 访问点。"""
    points: list[tuple[str, int, str]] = []
    for py in _iter_py(APP_ROOT):
        tree = _parse(py)
        if tree is None:
            continue
        rel = _rel(py)
        # 模块级常量映射（ENV_KEY = "LITERAL"），解析 os.environ.get(ENV_KEY) 形式
        constants: dict[str, str] = {}
        for stmt in tree.body:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                constants[stmt.targets[0].id] = stmt.value.value

        def _resolve(arg: ast.expr | None) -> str | None:
            if arg is None:
                return None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
            if isinstance(arg, ast.Name) and arg.id in constants:
                return constants[arg.id]
            return None

        for node in ast.walk(tree):
            key: str | None = None
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr == "getenv"
            ):
                key = _resolve(node.args[0] if node.args else None)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "environ"
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "os"
            ):
                key = _resolve(node.args[0] if node.args else None)
            elif (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "environ"
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os"
            ):
                key = _resolve(node.slice)
            if key is not None:
                points.append((rel, node.lineno, key))
    return points


def test_all_settings_fields_are_referenced() -> None:
    """死配置即红灯：Settings 每个字段必须至少被 app/ 或 scripts/ 引用一处。"""
    fields = _settings_fields()
    assert fields, "Settings 类未扫描到任何字段，契约测试自身失效"
    refs = _collect_field_refs(fields)
    unreferenced = [f for f in fields if not refs[f]]
    assert not unreferenced, (
        "以下 Settings 字段无业务引用（死配置）:\n"
        + "\n".join(f"  - {f}" for f in sorted(unreferenced))
    )


def test_env_access_within_whitelist() -> None:
    """env 直读即红灯：app/ 下 os.getenv/os.environ 访问点必须落在 C1 §2.4 白名单。"""
    points = _env_access_points()
    violations = [
        (rel, lineno, key)
        for rel, lineno, key in points
        if (rel, key) not in ENV_WHITELIST
    ]
    assert not violations, (
        "以下 os.getenv/os.environ 访问点绕过 settings（不在白名单）:\n"
        + "\n".join(f"  - {rel}:{lineno} -> {key}" for rel, lineno, key in violations)
    )


def test_whitelist_entries_are_present() -> None:
    """白名单每项都必须真实存在，防止白名单与代码漂移（白名单失效）。"""
    points = _env_access_points()
    observed = {(rel, key) for rel, _, key in points}
    missing = ENV_WHITELIST - observed
    assert not missing, (
        "C1 白名单项在代码中不存在（白名单过时）:\n"
        + "\n".join(f"  - {rel}:{key}" for rel, key in sorted(missing))
    )


def test_app_py_files_are_parseable() -> None:
    """app/ 下所有 .py 必须可 AST 解析，保证扫描无盲区。"""
    unparsable = [
        _rel(py) for py in _iter_py(APP_ROOT) if _parse(py) is None
    ]
    assert not unparsable, (
        "以下 app/ 文件无法 AST 解析，引用扫描有盲区:\n"
        + "\n".join(f"  - {p}" for p in unparsable)
    )
