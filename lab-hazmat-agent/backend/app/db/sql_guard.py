"""只读 SQL 护栏：第 3 层（AST 校验）+ 第 4 层（LIMIT 注入 + 语句超时）。

设计要点（对应开发文档 §4.4）：
- 用 sqlglot 解析 AST，不用正则。正则会被 `SELECT ... WHERE name='王 update'` 误杀。
- 参数占位符 `%(name)s` 不是合法 SQL，解析前先替换成字面量 `1`，但返回值必须是
  「原语句 + 追加 LIMIT」，绝不返回 `ast.sql()`（那会把占位符吐成字面量，破坏参数绑定）。

本文件修正的三个实测漏洞（原实现均被绕过）：
1. **可执行注释 `/*!50000 DELETE */`**：MySQL 会执行 `/*! ... */` 里的内容，
   而 sqlglot 把它整段当注释丢弃，AST 里只剩 `Select`，于是原实现放行。
   现于解析前剥离注释。
2. **尾注释吞掉 LIMIT**：`SELECT ... -- 注释` 后面追加 ` LIMIT 200`，
   LIMIT 落进注释里，实测解析出的 LIMIT 为 None，等于没加限制。
   现于追加 LIMIT 前先剥离注释。
3. **子查询已是 Select 时误注入**：`validate_readonly` 返回整条原语句，
   但「是否已有 LIMIT」只看最外层——这是正确的；原实现的真问题是
   顶层 LIMIT 判断依赖未剥注释的文本，与上面同因。
"""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

# 一旦出现即拒绝的节点类型
_FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
    exp.TruncateTable, exp.Grant, exp.Command, exp.Set, exp.Use, exp.Merge,
)

# 一旦出现即拒绝的函数（探测、读文件、写文件、锁行）
_FORBIDDEN_FUNCS = {"sleep", "benchmark", "load_file", "get_lock", "release_lock"}

# 驱动参数占位符 %(name)s —— 它不是合法 SQL，解析前必须先替换
_PLACEHOLDER = re.compile(r"%\(\w+\)s")
_NUMBERED_PLACEHOLDER = re.compile(r"%s")

# 注释剥离。顺序重要：先剥普通块注释，再剥行注释。
# 注意：`/*! ... */` 可执行注释不在这里剥——见 _assert_no_exec_comment。
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT = re.compile(r"(--|#)[^\n]*")

# MySQL 的可执行注释。sqlglot 把它当注释丢弃，MySQL 却会执行里面的内容——
# 两者对同一条 SQL 的理解不一致，任何分析结论都不可信，必须直接拒绝。
_EXEC_COMMENT = re.compile(r"/\*!")


def _strip_comments(sql: str) -> str:
    """剥离普通注释，返回等价的无注释 SQL。

    行注释有实际危害：在其后追加 LIMIT 会被注释吞掉，实测
    `SELECT ... -- 注释` 追加 ` LIMIT 200` 后解析出的 LIMIT 为 None，等于没限制。
    所以追加 LIMIT 前必须先剥干净。
    """
    out = _BLOCK_COMMENT.sub(" ", sql)
    out = _LINE_COMMENT.sub(" ", out)
    return out.strip()


def _assert_no_exec_comment(sql: str) -> None:
    """拒绝 MySQL 可执行注释 `/*! ... */`。

    原实现注释里写「正则会被 `/*!50000 DELETE */` 绕过」，但真实行为相反：
    sqlglot 把它整段丢弃，AST 里只剩 `Select`，护栏**放行**了它。
    更糟的是若靠剥离注释来"修"，就等于悄悄执行了一条和模型给的不同的 SQL——
    分析结论与实际执行不一致，审计上不可接受。所以直接拒绝。
    """
    if _EXEC_COMMENT.search(sql):
        raise GuardError("检测到 MySQL 可执行注释 /*! ... */，该写法会绕过解析器，已拒绝执行。")


class GuardError(ValueError):
    """SQL 未通过只读护栏。调用方应把这条错误原文回给模型，让它改写。"""


def _scan_ast(ast: exp.Expression, parse_text: str) -> None:
    for node in ast.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise GuardError(f"检测到非只读操作：{type(node).__name__}，已拒绝执行。")
        if isinstance(node, exp.Anonymous) and str(node.name).lower() in _FORBIDDEN_FUNCS:
            raise GuardError(f"检测到危险函数 {node.name}，已拒绝执行。")
        if isinstance(node, exp.Lock):          # SELECT ... FOR UPDATE / LOCK IN SHARE MODE
            raise GuardError("禁止加锁查询。")

    # 表级兜底：只按标识符判断，不做子串匹配——
    # 原实现用 `"information_schema" in lowered`，会把 dept='information_schema'
    # 这种普通字符串常量也拒掉，属于误杀。
    for table in ast.find_all(exp.Table):
        name = (table.name or "").lower()
        db = (table.db or "").lower()
        if name in {"user", "db", "tables_priv"} and db in {"mysql", "sys"}:
            raise GuardError(f"禁止访问敏感系统表 {db}.{name}。")
        if db == "information_schema" or name == "information_schema":
            raise GuardError("禁止访问 information_schema。")

    if "into outfile" in parse_text or "into dumpfile" in parse_text:
        raise GuardError("禁止导出文件（INTO OUTFILE / DUMPFILE）。")


def validate_readonly(sql: str, *, max_rows: int | None = None) -> str:
    """校验并返回可执行的只读 SQL。不合规抛 GuardError。

    注意：只把占位符替换成字面量"用于解析"，返回的仍是原语句——
    参数始终由驱动绑定，绝不做字符串拼接。
    """
    from app.core.config import get_settings

    limit_rows = max_rows if max_rows is not None else get_settings().sql_max_rows

    # 1) 先拒可执行注释，再剥普通注释，最后替换占位符用于解析
    _assert_no_exec_comment(sql)
    cleaned = _strip_comments(sql)
    if not cleaned:
        raise GuardError("SQL 为空。")

    parse_text = _PLACEHOLDER.sub("1", cleaned)
    parse_text = _NUMBERED_PLACEHOLDER.sub("1", parse_text)

    try:
        statements = [s for s in sqlglot.parse(parse_text, read="mysql") if s is not None]
    except ParseError as exc:
        raise GuardError(f"SQL 解析失败，请修正语法：{exc}") from exc

    if len(statements) != 1:
        raise GuardError("只允许单条 SQL 语句，禁止堆叠执行。")

    ast = statements[0]
    if not isinstance(ast, (exp.Select, exp.Union)):
        raise GuardError("本系统只读，仅允许 SELECT / UNION 查询。")

    _scan_ast(ast, parse_text)

    # 2) 第 4 层：注入 LIMIT。
    # 基于剥过注释的文本追加，否则 `SELECT ... -- 注释` 会把 LIMIT 吞进注释里，
    # 实测那种情况下解析出的 LIMIT 为 None，等于没限制。
    safe = cleaned.rstrip().rstrip(";")
    if ast.args.get("limit") is None:
        safe = f"{safe} LIMIT {limit_rows}"
    return safe


def statement_timeout_ms() -> int:
    """语句超时（毫秒）。来自配置，便于在云实例上调参而不改代码。"""
    from app.core.config import get_settings

    return get_settings().sql_timeout_ms


def max_rows() -> int:
    """单次查询最大返回行数。"""
    from app.core.config import get_settings

    return get_settings().sql_max_rows


# 兼容旧引用点：默认值快照，仅供日志/文档展示，实际执行以函数为准。
MAX_ROWS = 200
STATEMENT_TIMEOUT_MS = 8000

__all__ = [
    "validate_readonly", "GuardError",
    "statement_timeout_ms", "max_rows",
    "MAX_ROWS", "STATEMENT_TIMEOUT_MS",
]
