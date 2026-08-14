"""M9-P0-2 · nginx 上传体积上限对齐测试（P0-15）。

背景：nginx 未声明 ``client_max_body_size`` 时默认 1MB，而业务
``upload_max_bytes`` 为 20MB，>1MB 文档会在反代层被拒。
本测试纯静态解析，不启动容器，断言：
1. ``docker/nginx/default.conf`` 声明了 ``client_max_body_size``；
2. 其字节上限不小于 ``app/core/config.py`` 中 ``upload_max_bytes`` 的求值；
3. 上限至少有一条位于 server/http 层（不在 location 内被收窄）。
测试失败 = nginx 层上传容量与业务配置再次漂移（CI 红）。
"""

from __future__ import annotations

import ast
import pathlib
import re


BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
NGINX_CONF = REPO_ROOT / "docker" / "nginx" / "default.conf"
CONFIG_PY = BACKEND_ROOT / "app" / "core" / "config.py"

_CLIENT_MAX_BODY_RE = re.compile(
    r"client_max_body_size\s+(?P<number>\d+)(?P<unit>[kKmMgG]?)\s*;"
)
_UNIT_TO_MULTIPLIER = {
    "": 1,
    "k": 1024,
    "K": 1024,
    "m": 1024 * 1024,
    "M": 1024 * 1024,
    "g": 1024 * 1024 * 1024,
    "G": 1024 * 1024 * 1024,
}


def _read_utf8(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _nginx_directives(text: str) -> list[tuple[int, int, int]]:
    """返回 (行号, 字节上限)，仅识别非注释行的顶层/块级指令。"""
    found: list[tuple[int, int]] = []
    depth = 0
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        code = raw.split("#", 1)[0]
        depth += code.count("{") - code.count("}")
        m = _CLIENT_MAX_BODY_RE.search(code)
        if m is None:
            continue
        number = int(m.group("number"))
        multiplier = _UNIT_TO_MULTIPLIER[m.group("unit")]
        # 指令生效深度：server 块为 1，http 块为 0；location 内为 >=2。
        found.append((lineno, depth, number * multiplier))
    return found


def _eval_upload_max_bytes(node: ast.expr) -> int:
    """安全求值 config.py 中 upload_max_bytes 的字面量表达式。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.BinOp):
        left = _eval_upload_max_bytes(node.left)
        right = _eval_upload_max_bytes(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_upload_max_bytes(node.operand)
    raise AssertionError(f"upload_max_bytes 含未支持表达式: {ast.dump(node)}")


def _business_upload_limit() -> int:
    tree = ast.parse(_read_utf8(CONFIG_PY))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for stmt in node.body:
                if (
                    isinstance(stmt, ast.AnnAssign)
                    and isinstance(stmt.target, ast.Name)
                    and stmt.target.id == "upload_max_bytes"
                    and stmt.value is not None
                ):
                    return _eval_upload_max_bytes(stmt.value)
    raise AssertionError("config.py 未声明 upload_max_bytes")


def test_nginx_declares_client_max_body_size() -> None:
    directives = _nginx_directives(_read_utf8(NGINX_CONF))
    assert directives, (
        "docker/nginx/default.conf 未声明 client_max_body_size，"
        "nginx 默认 1MB 会拒绝 >1MB 上传"
    )


def test_nginx_upload_limit_meets_business_limit() -> None:
    directives = _nginx_directives(_read_utf8(NGINX_CONF))
    business_limit = _business_upload_limit()
    assert directives, "nginx 未声明 client_max_body_size"
    max_limit = max(limit for _, _, limit in directives)
    assert max_limit >= business_limit, (
        f"nginx client_max_body_size={max_limit}B < 业务 "
        f"upload_max_bytes={business_limit}B"
    )


def test_nginx_upload_limit_not_narrowed_in_location() -> None:
    directives = _nginx_directives(_read_utf8(NGINX_CONF))
    business_limit = _business_upload_limit()
    server_level = [limit for _, depth, limit in directives if depth <= 1]
    assert server_level, (
        "client_max_body_size 只出现在 location 内，server/http 层仍为默认 1MB"
    )
    assert max(server_level) >= business_limit
