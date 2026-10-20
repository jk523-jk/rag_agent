"""aiomysql 连接池 + 会话只读（第 2 层）+ 统一取数入口。

云数据库适配（对接云 MySQL 的三处关键差异）：
1. 首包延迟：云公网实例 TLS 握手 + 网络往返可达数百毫秒，`connect_timeout` 放宽，
   并用 `pool_recycle` 主动回收连接，避免被云侧空闲断开后拿到死连接。
2. TLS：云厂商普遍要求或建议加密连接，ssl 参数由 config 的 mysql_ssl_args 提供。
3. 会话变量：`MAX_EXECUTION_TIME` 在部分云托管实例（如只读实例、代理模式）可能被
   限制。设置失败不再让整个查询失败，降级为告警——语句超时在护栏侧已有 8s 兜底。
"""
from __future__ import annotations

import asyncio
import logging
from time import monotonic

import aiomysql

from app.core.config import get_settings
from app.db.sql_guard import GuardError, statement_timeout_ms, validate_readonly

log = logging.getLogger(__name__)

_pool: aiomysql.Pool | None = None
_pool_lock = asyncio.Lock()
_last_pool_attempt: float | None = None
_POOL_RETRY_INTERVAL = 8.0


async def init_pool() -> None:
    """建连接池。连不上时**不让进程起不来**——health 会报 degraded，
    这样运维能直接 curl /api/health 看到确切原因，而不是容器反复重启看不出所以然。"""
    global _pool, _last_pool_attempt
    async with _pool_lock:
        if _pool is not None and not _pool.closed:
            return
        now = monotonic()
        if (_last_pool_attempt is not None
                and now - _last_pool_attempt < _POOL_RETRY_INTERVAL):
            return
        s = get_settings()
        try:
            _pool = await aiomysql.create_pool(
                host=s.mysql_host,
                port=s.mysql_port,
                user=s.mysql_user,
                password=s.mysql_password,
                db=s.mysql_db,
                charset=s.mysql_charset,
                autocommit=True,
                minsize=s.mysql_pool_min,
                maxsize=s.mysql_pool_max,
                pool_recycle=s.mysql_pool_recycle,
                connect_timeout=s.mysql_connect_timeout,
                **s.mysql_ssl_args,
            )
        except Exception as exc:                                  # noqa: BLE001
            _pool = None
            _last_pool_attempt = now
            log.error(
                "MySQL 连接失败 endpoint=%s ssl=%s err=%s: %s",
                s.mysql_endpoint, bool(s.mysql_ssl_args), type(exc).__name__, exc,
            )
            return
        _last_pool_attempt = None
        log.info("MySQL 连接池就绪 endpoint=%s ssl=%s", s.mysql_endpoint, bool(s.mysql_ssl_args))


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


def pool_ready() -> bool:
    return _pool is not None and not _pool.closed


async def ping() -> bool:
    """真实探活（连通性检查，不走只读护栏），供热力检查与 /api/health 使用。"""
    if _pool is None or _pool.closed:
        await init_pool()
        if _pool is None or _pool.closed:
            return False
    try:
        async with _pool.acquire() as conn:
            await conn.ping(reconnect=True)
        return True
    except Exception as exc:                                      # noqa: BLE001
        log.warning("MySQL ping 失败：%s: %s", type(exc).__name__, exc)
        return False


async def fetch_all(sql: str, params: dict | None = None) -> list[dict]:
    """唯一的数据读取入口。所有工具都必须走这里，不允许自行开连接。"""
    if _pool is None or _pool.closed:
        await init_pool()
    if _pool is None or _pool.closed:
        raise RuntimeError("数据库连接池不可用，请检查 MYSQL_HOST/账号/网络与 MYSQL_SSL 配置。")

    s = get_settings()
    safe_sql = validate_readonly(sql)

    async with _pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # 第 2 层：会话级只读。云实例若禁止会话变量，降级为告警而非中断。
            for stmt in (
                "SET SESSION TRANSACTION READ ONLY",
                f"SET SESSION MAX_EXECUTION_TIME={statement_timeout_ms()}",
            ):
                try:
                    await cur.execute(stmt)
                except Exception as exc:                          # noqa: BLE001
                    log.warning("会话变量设置失败（已跳过）%s：%s", stmt, type(exc).__name__)
                    break
            await cur.execute(safe_sql, params or {})
            return list(await cur.fetchall())


async def describe_connection() -> dict:
    """自检用：返回当前连接的实际参数（不含口令），便于确认连到了哪个云实例。"""
    try:
        rows = await fetch_all(
            "SELECT VERSION() AS version, DATABASE() AS db, CURRENT_USER() AS user, "
            "  @@hostname AS hostname, @@read_only AS read_only"
        )
    except Exception as exc:                                      # noqa: BLE001
        return {"connected": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"connected": True, **(rows[0] if rows else {})}


__all__ = [
    "init_pool", "close_pool", "fetch_all", "ping", "pool_ready", "describe_connection",
    "GuardError", "validate_readonly",
]
