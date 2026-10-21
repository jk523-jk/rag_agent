"""显式数据源及统一个人/管理范围。不会因数据源失败而回退到初始化数据。"""
from __future__ import annotations

import json
from datetime import date, timedelta

from app.core.config import get_settings
from app.portal.auth import Principal, fail
from app.portal.store import connection, notify, now, today

COLLECTIONS = ("labs", "persons", "qualifications", "authorizations", "accessEvents",
               "inventory", "hazmatUses", "equipment", "equipmentLoans")


async def snapshot() -> dict:
    source = get_settings().business_data_source
    if source == "application":
        with connection() as db:
            row = db.execute("SELECT payload,updated_at FROM business_data WHERE id=1").fetchone()
        if not row:
            fail(503, "DATA_NOT_INITIALIZED", "业务数据尚未初始化，请联系管理员执行初始化命令")
        data = json.loads(row["payload"])
        return {**data, "serverTime": now(), "updatedAt": row["updated_at"], "source": "application"}
    if source == "mysql":
        from app.api import data as legacy
        return {"labs": await legacy._labs(), "persons": await legacy._persons(),
                "qualifications": await legacy._qualifications(), "authorizations": await legacy._authorizations(),
                "accessEvents": await legacy._access_events(500), "inventory": await legacy._inventory(),
                "hazmatUses": await legacy._hazmat_uses(), "equipment": await legacy._equipment(),
                "equipmentLoans": await legacy._equipment_loans(), "serverTime": now(),
                "source": "mysql", "accessEventsTruncated": True}
    fail(503, "DATA_SOURCE_INVALID", "业务数据源配置不正确")


def scoped(data: dict, p: Principal) -> dict:
    if p.role == "admin" and p.system_admin:
        return data
    result = {**data}
    if p.role == "admin":
        labs = set(p.lab_ids)
        persons = {a["personId"] for a in data["authorizations"] if a["labId"] in labs}
        persons |= {a["personId"] for a in data["accessEvents"] if a["labId"] in labs}
        persons |= {e["keeperId"] for e in data["equipment"] if e["labId"] in labs and e.get("keeperId")}
        assigned_equipment = {e["equipId"] for e in data["equipment"] if e["labId"] in labs}
        assigned_items = {e["id"] for e in data["inventory"] if e["labId"] in labs}
        persons |= {l["personId"] for l in data["equipmentLoans"] if l["equipId"] in assigned_equipment}
        persons |= {u["personId"] for u in data["hazmatUses"] if u["itemId"] in assigned_items}
        with connection() as db:
            persons |= {r[0] for r in db.execute("SELECT person_id FROM applications WHERE lab_id IN (" + ",".join("?" for _ in labs) + ")", tuple(labs))} if labs else set()
        result["persons"] = [v for v in data["persons"] if v["id"] in persons]
        result["qualifications"] = [v for v in data["qualifications"] if v["personId"] in persons]
        for key in ("labs", "authorizations", "accessEvents", "inventory", "equipment"):
            result[key] = [v for v in data[key] if v["labId"] in labs]
    else:
        labs = {v["labId"] for v in data["authorizations"] if v["personId"] == p.person_id}
        result["labs"] = [v for v in data["labs"] if v["labId"] in labs]
        result["persons"] = [v for v in data["persons"] if v["id"] == p.person_id]
        for key in ("qualifications", "authorizations", "accessEvents", "equipmentLoans", "hazmatUses"):
            result[key] = [v for v in data[key] if v["personId"] == p.person_id]
        borrowed = {v["equipId"] for v in result["equipmentLoans"]}
        result["equipment"] = [v for v in data["equipment"] if v["equipId"] in borrowed]
        result["inventory"] = []
    equip_ids = {v["equipId"] for v in result["equipment"]}
    item_ids = {v["id"] for v in result["inventory"]}
    if p.role == "admin":
        result["equipmentLoans"] = [v for v in data["equipmentLoans"] if v["equipId"] in equip_ids]
        result["hazmatUses"] = [v for v in data["hazmatUses"] if v["itemId"] in item_ids]
    return result


def person(data: dict, person_id: str) -> dict:
    row = next((v for v in data["persons"] if v["id"] == person_id), None)
    if not row:
        fail(409, "PERSON_NOT_LINKED", "账号尚未关联有效人员档案，请联系管理员")
    return row


def qualification_issues(data: dict, person_id: str, lab_id: str, until: str | None = None, on_date: str | None = None) -> list[str]:
    lab = next((v for v in data["labs"] if v["labId"] == lab_id), None)
    if not lab:
        return ["实验室不存在"]
    if lab.get("status", "开放") != "开放":
        return ["实验室当前暂停申请与准入"]
    required = lab.get("requiredCerts", ["安全考试合格证"])
    anchor = on_date or today()
    issues = []
    for cert in required:
        valid = any(q["personId"] == person_id and q["certType"] == cert and q["status"] == "有效"
                    and q["issueDate"] <= anchor and q["expireDate"] >= (until or anchor)
                    for q in data["qualifications"])
        if not valid:
            issues.append(f"{cert}缺失、已失效或未覆盖申请结束日期")
    return issues


def permit_status(data: dict, grant: dict) -> str:
    if grant["status"] in {"已撤销", "已注销"}:
        return "已撤销"
    if grant["authTo"] < today():
        return "已到期"
    if grant["authFrom"] > today():
        return "未到生效时间"
    issues = qualification_issues(data, grant["personId"], grant["labId"])
    return "条件不满足" if issues else "有效"


def reminders(data: dict, p: Principal):
    with connection() as db:
        for key, end_field, id_field, label in (("qualifications", "expireDate", "id", "资质"), ("authorizations", "authTo", "id", "许可")):
            for value in data[key]:
                if value["personId"] != p.person_id or value.get("status") != "有效":
                    continue
                days = (date.fromisoformat(value[end_field]) - date.fromisoformat(today())).days
                if days in (30, 7, 1, 0):
                    notify(db, p.id, f"{label}到期提醒", f"{value.get('certType', value.get('labId', ''))} 将于 {value[end_field]} 到期",
                           dedupe_key=f"{p.id}:{key}:{value[id_field]}:{value[end_field]}:{days}")


def save_snapshot(db, data: dict):
    payload = {k: data[k] for k in COLLECTIONS}
    db.execute("INSERT OR REPLACE INTO business_data VALUES(1,?,?)", (json.dumps(payload, ensure_ascii=False), now()))
