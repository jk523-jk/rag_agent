"""只读数据接口：把 lab_hazmat 库的真实数据供给前端控制台。

与 Agent 工具层的分工：
- 工具层面向**大模型**，返回值必须脱敏（剧毒品/易制爆数量区间化），避免精确存量进入模型上下文；
- 本模块面向**管理工作台**，登录用户本就是实验室管理者，需要看到完整台账数字。
  因此这里不做区间化，但仍严格遵守「只读」——全部是固化的 SELECT，不接受任何外部拼接。

字段一律转成前端 `@/types` 的 camelCase 形态，避免前端再做一层映射。
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query

from app.db.connection import fetch_all, pool_ready
from app.db.sql_guard import GuardError

router = APIRouter(prefix="/data", tags=["data"])
log = logging.getLogger("app.api.data")

MAX_ROWS = 500


# ---------------------------------------------------------------- 序列化辅助
def _d(v) -> str | None:
    """日期 → 'YYYY-MM-DD'。"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    return str(v)


def _dt(v) -> str | None:
    """时间 → 'YYYY-MM-DD HH:MM'，前端按字符串排序与展示。"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    return str(v)


def _num(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    return None


async def _q(sql: str, params: dict | None = None) -> list[dict]:
    """统一取数：库未就绪直接 503，护栏拦截转 500 并记日志。"""
    if not pool_ready():
        raise HTTPException(status_code=503, detail="数据库未就绪，请查看 /api/health")
    try:
        return await fetch_all(sql, params)
    except GuardError as e:                     # 理论上不会发生：SQL 全是本文件常量
        log.error("只读护栏拦截了内置 SQL: %s", e)
        raise HTTPException(status_code=500, detail="内置查询被只读护栏拦截")
    except Exception as e:                       # 连接中断等
        log.error("数据查询失败: %s", e)
        raise HTTPException(status_code=503, detail=f"数据查询失败：{type(e).__name__}")


# ---------------------------------------------------------------- 各资源
async def _labs() -> list[dict]:
    rows = await _q(
        "SELECT lab_id, lab_name, hazmat_class, needs_double, mgr_name "
        "FROM labs ORDER BY lab_id"
    )
    return [
        {
            "labId": r["lab_id"],
            "labName": r["lab_name"],
            "hazmatClass": r["hazmat_class"] or "",
            "needsDouble": bool(r["needs_double"]),
            "mgrName": r["mgr_name"] or "",
        }
        for r in rows
    ]


async def _persons() -> list[dict]:
    rows = await _q("SELECT id, name, emp_no, dept, role FROM persons ORDER BY id")
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "empNo": r["emp_no"] or "",
            "dept": r["dept"] or "",
            "role": r["role"] or "",
        }
        for r in rows
    ]


async def _qualifications() -> list[dict]:
    rows = await _q(
        "SELECT person_id, cert_type, cert_no, issue_date, expire_date, status "
        "FROM qualifications ORDER BY person_id, expire_date DESC"
    )
    return [
        {
            # 表上是联合主键，没有代理 id；用「人员+证书号」合成稳定标识
            "id": f"q-{r['person_id']}-{r['cert_no']}",
            "personId": str(r["person_id"]),
            "certType": r["cert_type"],
            "certNo": r["cert_no"] or "",
            "issueDate": _d(r["issue_date"]),
            "expireDate": _d(r["expire_date"]),
            "status": r["status"],
        }
        for r in rows
    ]


async def _authorizations() -> list[dict]:
    rows = await _q(
        "SELECT person_id, lab_id, auth_from, auth_to, grantor, status "
        "FROM lab_authorizations ORDER BY person_id, lab_id"
    )
    return [
        {
            "id": f"a-{r['person_id']}-{r['lab_id']}",
            "personId": str(r["person_id"]),
            "labId": r["lab_id"],
            "authFrom": _d(r["auth_from"]),
            "authTo": _d(r["auth_to"]),
            "grantor": r["grantor"] or "",
            "status": r["status"],
        }
        for r in rows
    ]


async def _access_events(limit: int) -> list[dict]:
    rows = await _q(
        "SELECT id, person_id, lab_id, event_time, direction, auth_type, auth_result, companion_no "
        "FROM access_events ORDER BY event_time DESC LIMIT %(limit)s",
        {"limit": limit},
    )
    return [
        {
            "id": f"e-{r['id']}",
            "personId": str(r["person_id"]),
            "labId": r["lab_id"],
            "eventTime": _dt(r["event_time"]),
            "direction": r["direction"],
            "authType": r["auth_type"],
            "authResult": r["auth_result"],
            "companionNo": r["companion_no"],
        }
        for r in rows
    ]


async def _inventory() -> list[dict]:
    rows = await _q(
        "SELECT item_id, chem_name, cas_no, hazard_class, lab_id, cabinet_no, quantity, unit, updated_at "
        "FROM hazmat_inventory ORDER BY item_id"
    )
    return [
        {
            "id": str(r["item_id"]),
            "chemName": r["chem_name"],
            "casNo": r["cas_no"] or "",
            "hazardClass": r["hazard_class"] or "",
            "labId": r["lab_id"],
            "cabinetNo": r["cabinet_no"] or "",
            "quantity": _num(r["quantity"]),
            "unit": r["unit"],
            "updatedAt": _dt(r["updated_at"]),
        }
        for r in rows
    ]


async def _hazmat_uses() -> list[dict]:
    rows = await _q(
        "SELECT id, item_id, person_id, use_time, quantity, witness_id, purpose "
        "FROM hazmat_uses ORDER BY use_time DESC"
    )
    return [
        {
            "id": f"u-{r['id']}",
            "itemId": str(r["item_id"]),
            "personId": str(r["person_id"]),
            "useTime": _d(r["use_time"]),
            "quantity": _num(r["quantity"]),
            "witnessId": str(r["witness_id"]) if r["witness_id"] is not None else None,
            "purpose": r["purpose"] or "",
        }
        for r in rows
    ]


async def _equipment() -> list[dict]:
    rows = await _q(
        "SELECT equip_id, equip_name, category, model_no, lab_id, keeper_id, status, "
        "calibrate_due, purchase_date, remark FROM equipment ORDER BY equip_id"
    )
    return [
        {
            "id": r["equip_id"],
            "equipId": r["equip_id"],
            "equipName": r["equip_name"],
            "category": r["category"] or "",
            "modelNo": r["model_no"] or "",
            "labId": r["lab_id"],
            "keeperId": str(r["keeper_id"]) if r["keeper_id"] is not None else None,
            "status": r["status"],
            "calibrateDue": _d(r["calibrate_due"]),
            "purchaseDate": _d(r["purchase_date"]),
            "remark": r["remark"] or "",
        }
        for r in rows
    ]


async def _equipment_loans() -> list[dict]:
    rows = await _q(
        "SELECT id, equip_id, person_id, borrow_time, due_time, return_time, purpose, approver, status "
        "FROM equipment_loans ORDER BY borrow_time DESC"
    )
    return [
        {
            "id": f"l-{r['id']}",
            "equipId": r["equip_id"],
            "personId": str(r["person_id"]),
            "borrowTime": _dt(r["borrow_time"]),
            "dueTime": _dt(r["due_time"]),
            "returnTime": _dt(r["return_time"]),
            "purpose": r["purpose"] or "",
            "approver": r["approver"] or "",
            "status": r["status"],
        }
        for r in rows
    ]


# ---------------------------------------------------------------- 路由
@router.get("/overview")
async def overview(access_limit: int = Query(200, ge=1, le=MAX_ROWS)) -> dict:
    """一次性返回控制台所需的全部领域数据，供前端 store 初始化。

    拆成多接口会让首屏发 9 个请求；工作台是「打开即全量」的使用方式，
    聚合成一个往返更合适，后续需要局部刷新再走下面的单资源接口。
    """
    return {
        "labs": await _labs(),
        "persons": await _persons(),
        "qualifications": await _qualifications(),
        "authorizations": await _authorizations(),
        "accessEvents": await _access_events(access_limit),
        "inventory": await _inventory(),
        "hazmatUses": await _hazmat_uses(),
        "equipment": await _equipment(),
        "equipmentLoans": await _equipment_loans(),
        "serverTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "mysql",
    }


@router.get("/labs")
async def labs() -> list[dict]:
    return await _labs()


@router.get("/persons")
async def persons() -> list[dict]:
    return await _persons()


@router.get("/qualifications")
async def qualifications() -> list[dict]:
    return await _qualifications()


@router.get("/authorizations")
async def authorizations() -> list[dict]:
    return await _authorizations()


@router.get("/access-events")
async def access_events(limit: int = Query(200, ge=1, le=MAX_ROWS)) -> list[dict]:
    return await _access_events(limit)


@router.get("/inventory")
async def inventory() -> list[dict]:
    return await _inventory()


@router.get("/hazmat-uses")
async def hazmat_uses() -> list[dict]:
    return await _hazmat_uses()


@router.get("/equipment")
async def equipment() -> list[dict]:
    return await _equipment()


@router.get("/equipment-loans")
async def equipment_loans() -> list[dict]:
    return await _equipment_loans()
