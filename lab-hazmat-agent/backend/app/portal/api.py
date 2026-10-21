from __future__ import annotations

import base64
import binascii
import json
import secrets
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.portal.auth import Principal, admin, current, fail, hash_password, system_admin
from app.portal.business import person, permit_status, qualification_issues, reminders, save_snapshot, scoped, snapshot
from app.portal.store import audit, connection, event, notify, now, today

router = APIRouter(tags=["portal"])


def owned(db, app_id: str, p: Principal, reviewing: bool = False):
    row = db.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    if not row or (not reviewing and row["user_id"] != p.id) or (reviewing and not p.can_lab(row["lab_id"])):
        fail(404, "NOT_FOUND", "记录不存在或不在可访问范围")
    return row


def expire(db):
    for row in db.execute("SELECT * FROM applications WHERE end_date<? AND status IN ('待审批','待补充')", (today(),)).fetchall():
        db.execute("UPDATE applications SET status='已失效',version=version+1,updated_at=? WHERE id=?", (now(), row["id"]))
        event(db, row["id"], "system", "申请失效", "申请结束日期已过")
        notify(db, row["user_id"], "申请已失效", "申请结束日期已过，请根据实验计划重新申请", row["id"])


def check_version(row, version: int):
    if row["version"] != version:
        fail(409, "VERSION_CONFLICT", "记录已被更新，请刷新后重试")


def serialize(db, row):
    result = dict(row)
    result["events"] = [dict(r) for r in db.execute("SELECT e.*,COALESCE(u.display_name,e.actor_id) AS actor_name "
                                                   "FROM application_events e LEFT JOIN users u ON e.actor_id=u.id "
                                                   "WHERE application_id=? ORDER BY e.id", (row["id"],))]
    result["attachments"] = [dict(r) for r in db.execute("SELECT id,name,media_type,created_at FROM attachments WHERE application_id=?", (row["id"],))]
    user = db.execute("SELECT display_name,username FROM users WHERE id=?", (row["user_id"],)).fetchone()
    result["applicant_name"] = user["display_name"] if user else row["person_id"]
    return result


@router.get("/me/summary")
async def summary(p: Principal = Depends(current)):
    data = await snapshot()
    profile = person(data, p.person_id)
    # A manager's personal portal is also restricted to their own identity.
    own = Principal(p.id, p.username, p.person_id, p.display_name, "user", False, [], p.must_change_password, p.csrf)
    result = scoped(data, own)
    result["profile"] = profile
    result["authorizations"] = [{**a, "effectiveStatus": permit_status(data, a),
                                  "issues": qualification_issues(data, p.person_id, a["labId"]),
                                  "hardwareStatus": "门禁下发未接入"} for a in result["authorizations"]]
    result["qualifications"] = [{**q, "effectiveStatus": "未生效" if q["issueDate"] > today() else "已过期" if q["expireDate"] < today() else q["status"]} for q in result["qualifications"]]
    reminders(data, p)
    with connection() as db:
        expire(db)
        result["pendingApplications"] = db.execute("SELECT count(*) FROM applications WHERE user_id=? AND status IN ('待审批','待补充')", (p.id,)).fetchone()[0]
        result["unreadNotifications"] = db.execute("SELECT count(*) FROM notifications WHERE user_id=? AND is_read=0", (p.id,)).fetchone()[0]
        result["permitHistory"] = [dict(r) for r in db.execute("SELECT id,lab_id,start_date,end_date,status,source_ref,created_at FROM permit_history WHERE person_id=? ORDER BY created_at DESC", (p.person_id,))]
    return result


@router.get("/me/profile")
async def profile(p: Principal = Depends(current)):
    return person(await snapshot(), p.person_id)


@router.get("/me/qualifications")
async def qualifications(p: Principal = Depends(current)):
    return (await summary(p))["qualifications"]


@router.get("/me/permits")
async def permits(p: Principal = Depends(current)):
    return (await summary(p))["authorizations"]


@router.get("/me/access-events")
async def access_events(page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100), p: Principal = Depends(current)):
    rows = sorted([v for v in (await snapshot())["accessEvents"] if v["personId"] == p.person_id], key=lambda v:v["eventTime"], reverse=True)
    return {"items": rows[(page-1)*page_size:page*page_size], "total": len(rows)}


@router.get("/me/equipment-loans")
async def equipment_loans(p: Principal = Depends(current)):
    return (await summary(p))["equipmentLoans"]


@router.get("/labs/available")
async def available(p: Principal = Depends(current)):
    data = await snapshot()
    person(data, p.person_id)
    return [{"labId": l["labId"], "labName": l["labName"], "status": l.get("status", "开放"),
             "needsDouble": l["needsDouble"], "requiredCerts": l.get("requiredCerts", ["安全考试合格证"]),
             "issues": qualification_issues(data, p.person_id, l["labId"])} for l in data["labs"]]


class ApplicationInput(BaseModel):
    labId: str = Field(min_length=1, max_length=32)
    kind: str = "新申请"
    purpose: str = Field(min_length=5, max_length=2000)
    startDate: date
    endDate: date
    version: int = Field(default=1, ge=1)


def validate_form(body: ApplicationInput, data: dict, p: Principal):
    person(data, p.person_id)
    if body.kind not in {"新申请", "续期"}:
        fail(422, "KIND_INVALID", "首版支持准入新申请和续期")
    if body.startDate > body.endDate or body.endDate.isoformat() < today():
        fail(422, "DATE_INVALID", "请填写有效的起止日期")
    if body.startDate.isoformat() < today():
        fail(422, "DATE_INVALID", "申请开始日期不能早于今天")
    lab = next((l for l in data["labs"] if l["labId"] == body.labId), None)
    if not lab or lab.get("status", "开放") != "开放":
        fail(422, "LAB_UNAVAILABLE", "该实验室不存在或已暂停开放")
    if body.kind == "续期" and not any(a["personId"] == p.person_id and a["labId"] == body.labId for a in data["authorizations"]):
        fail(422, "RENEWAL_INVALID", "尚无该实验室的历史许可，请选择新申请")


@router.post("/me/permit-applications")
async def create(body: ApplicationInput, p: Principal = Depends(current)):
    data = await snapshot()
    validate_form(body, data, p)
    app_id = "REQ-" + uuid.uuid4().hex[:12].upper()
    with connection() as db:
        db.execute("INSERT INTO applications(id,user_id,person_id,lab_id,kind,purpose,start_date,end_date,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                   (app_id, p.id, p.person_id, body.labId, body.kind, body.purpose.strip(), body.startDate.isoformat(), body.endDate.isoformat(), "草稿", now(), now()))
        event(db, app_id, p.id, "创建申请")
        return serialize(db, owned(db, app_id, p))


@router.patch("/me/permit-applications/{app_id}")
async def update(app_id: str, body: ApplicationInput, p: Principal = Depends(current)):
    validate_form(body, await snapshot(), p)
    with connection() as db:
        row = owned(db, app_id, p)
        check_version(row, body.version)
        if row["status"] not in {"草稿", "待补充"}:
            fail(409, "STATE_INVALID", "当前申请状态不允许编辑")
        db.execute("UPDATE applications SET lab_id=?,kind=?,purpose=?,start_date=?,end_date=?,version=version+1,updated_at=? WHERE id=?",
                   (body.labId, body.kind, body.purpose.strip(), body.startDate.isoformat(), body.endDate.isoformat(), now(), app_id))
        event(db, app_id, p.id, "更新申请")
        return serialize(db, owned(db, app_id, p))


def application_list(p: Principal, is_admin: bool, page: int, page_size: int, status: str, lab_id: str):
    with connection() as db:
        expire(db)
        where, args = [], []
        if not is_admin:
            where.append("user_id=?")
            args.append(p.id)
        elif not p.system_admin:
            where.append("lab_id IN (" + ",".join("?" for _ in p.lab_ids) + ")")
            args.extend(p.lab_ids)
        if status:
            where.append("status=?")
            args.append(status)
        if lab_id:
            where.append("lab_id=?")
            args.append(lab_id)
        clause = " WHERE " + " AND ".join(where) if where else ""
        total = db.execute("SELECT count(*) FROM applications"+clause, args).fetchone()[0]
        rows = db.execute("SELECT * FROM applications"+clause+" ORDER BY updated_at DESC,id LIMIT ? OFFSET ?", [*args, page_size, (page-1)*page_size]).fetchall()
        return {"items": [serialize(db, row) for row in rows], "total": total}


@router.get("/me/permit-applications")
def my_applications(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str = "", lab_id: str = "", p: Principal = Depends(current)):
    return application_list(p, False, page, page_size, status, lab_id)


@router.get("/admin/permit-applications")
def admin_applications(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str = "", lab_id: str = "", p: Principal = Depends(admin)):
    return application_list(p, True, page, page_size, status, lab_id)


@router.get("/me/permit-applications/{app_id}")
def my_application(app_id: str, p: Principal = Depends(current)):
    with connection() as db:
        return serialize(db, owned(db, app_id, p))


@router.get("/admin/permit-applications/{app_id}")
def admin_application(app_id: str, p: Principal = Depends(admin)):
    with connection() as db:
        return serialize(db, owned(db, app_id, p, True))


class Version(BaseModel):
    version: int = Field(ge=1)


@router.post("/me/permit-applications/{app_id}/submit")
async def submit(app_id: str, body: Version, p: Principal = Depends(current)):
    data = await snapshot()
    with connection() as db:
        row = owned(db, app_id, p)
        check_version(row, body.version)
        if row["status"] not in {"草稿", "待补充"}:
            fail(409, "STATE_INVALID", "申请已提交或已经结束")
        if row["end_date"] < today() or row["start_date"] < today():
            fail(422, "DATE_INVALID", "请更新申请起止日期后重新提交")
        issues = qualification_issues(data, p.person_id, row["lab_id"], row["end_date"])
        if issues:
            fail(422, "QUALIFICATION_REQUIRED", "；".join(issues))
        duplicate = db.execute("SELECT id FROM applications WHERE user_id=? AND lab_id=? AND id<>? "
                               "AND (status IN ('待审批','待补充') OR (status='已通过' AND execution_status<>'已撤销')) "
                               "AND start_date<=? AND end_date>=?", (p.id, row["lab_id"], app_id, row["end_date"], row["start_date"])).fetchone()
        if duplicate:
            fail(409, "DUPLICATE_APPLICATION", "相同时段已有处理中或已批准的申请")
        reviewers = [u for u in db.execute("SELECT * FROM users WHERE role='admin' AND active=1 AND id<>?", (p.id,))
                     if u["system_admin"] or row["lab_id"] in json.loads(u["lab_ids"])]
        if not reviewers:
            # Committed draft remains editable; return an explicit routing problem.
            fail(409, "REVIEWER_UNAVAILABLE", "暂未配置可用审批人，请联系管理员配置后再提交")
        db.execute("UPDATE applications SET status='待审批',version=version+1,updated_at=?,submitted_at=?,evidence_snapshot=? WHERE id=?",
                   (now(), now(), json.dumps({"qualifications": [q for q in data["qualifications"] if q["personId"] == p.person_id], "checkedAt": now()}, ensure_ascii=False), app_id))
        event(db, app_id, p.id, "提交申请")
        for reviewer in reviewers:
            notify(db, reviewer["id"], "新的许可申请", f"{p.display_name} 提交了 {row['lab_id']} 准入申请", app_id)
        return serialize(db, owned(db, app_id, p))


@router.post("/me/permit-applications/{app_id}/withdraw")
def withdraw(app_id: str, body: Version, p: Principal = Depends(current)):
    with connection() as db:
        row = owned(db, app_id, p)
        check_version(row, body.version)
        if row["status"] not in {"草稿", "待审批", "待补充"}:
            fail(409, "STATE_INVALID", "当前状态不能撤回")
        db.execute("UPDATE applications SET status='已撤回',version=version+1,updated_at=? WHERE id=?", (now(), app_id))
        event(db, app_id, p.id, "撤回申请")
        return serialize(db, owned(db, app_id, p))


class Review(Version):
    decision: str
    note: str = Field(default="", max_length=2000)


@router.post("/admin/permit-applications/{app_id}/review")
async def review(app_id: str, body: Review, p: Principal = Depends(admin)):
    data = await snapshot()
    if body.decision not in {"通过", "驳回", "补充材料"}:
        fail(422, "DECISION_INVALID", "请选择有效审批结果")
    if body.decision != "通过" and not body.note.strip():
        fail(422, "NOTE_REQUIRED", "请填写处理原因")
    with connection() as db:
        row = owned(db, app_id, p, True)
        check_version(row, body.version)
        if row["user_id"] == p.id:
            fail(403, "SELF_REVIEW_DENIED", "不能审批本人申请")
        if row["status"] != "待审批" or row["end_date"] < today():
            fail(409, "STATE_INVALID", "申请已处理或已失效")
        if body.decision == "通过":
            issues = qualification_issues(data, row["person_id"], row["lab_id"], row["end_date"])
            if issues:
                fail(422, "QUALIFICATION_REQUIRED", "；".join(issues))
        status = {"通过": "已通过", "驳回": "已驳回", "补充材料": "待补充"}[body.decision]
        execution = "待生效" if status == "已通过" else "未执行"
        db.execute("UPDATE applications SET status=?,execution_status=?,reviewer_id=?,version=version+1,updated_at=? WHERE id=?",
                   (status, execution, p.id, now(), app_id))
        event(db, app_id, p.id, "审批"+body.decision, body.note.strip())
        notify(db, row["user_id"], "许可申请处理结果", f"{app_id}：{status}。{body.note}", app_id)
        return serialize(db, owned(db, app_id, p, True))


class Execution(Version):
    reference: str = Field(min_length=3, max_length=200)


@router.post("/admin/permit-applications/{app_id}/execution-confirmation")
async def execute(app_id: str, body: Execution, p: Principal = Depends(admin)):
    data = await snapshot()
    with connection() as db:
        row = owned(db, app_id, p, True)
        if row["execution_status"] == "已生效":
            return serialize(db, row)  # retry is idempotent
        check_version(row, body.version)
        if row["status"] != "已通过" or row["end_date"] < today():
            fail(409, "STATE_INVALID", "仅能执行已批准且未失效的申请")
        issues = qualification_issues(data, row["person_id"], row["lab_id"], row["end_date"])
        if issues:
            fail(422, "QUALIFICATION_REQUIRED", "；".join(issues))
        if get_settings().business_data_source == "application":
            # Read inside transaction to prevent concurrent snapshot updates being lost.
            data = json.loads(db.execute("SELECT payload FROM business_data WHERE id=1").fetchone()[0])
            grant = next((a for a in data["authorizations"] if a["personId"] == row["person_id"] and a["labId"] == row["lab_id"]), None)
            values = {"id": f"a-{row['person_id']}-{row['lab_id']}", "personId": row["person_id"], "labId": row["lab_id"],
                      "authFrom": row["start_date"], "authTo": row["end_date"], "grantor": p.display_name, "status": "有效"}
            if grant:
                # Keep uninterrupted existing validity on renewal; retain original interval in audit.
                event(db, app_id, p.id, "原授权快照", json.dumps(grant, ensure_ascii=False))
                if grant["status"] == "有效" and grant["authTo"] >= row["start_date"]:
                    values["authFrom"] = min(grant["authFrom"], row["start_date"])
                    values["authTo"] = max(grant["authTo"], row["end_date"])
                grant.update(values)
            else:
                data["authorizations"].append(values)
            save_snapshot(db, data)
        else:
            if not any(a["personId"] == row["person_id"] and a["labId"] == row["lab_id"] and a["status"] == "有效"
                       and a["authFrom"] <= row["start_date"] and a["authTo"] >= row["end_date"] for a in data["authorizations"]):
                fail(409, "AUTHORIZATION_NOT_CONFIRMED", "尚未在业务授权台账中查到覆盖申请区间的有效授权，请先完成原渠道登记")
        db.execute("INSERT OR IGNORE INTO permit_history VALUES(?,?,?,?,?,?,?,?,?)", ("permit-"+app_id, app_id, row["person_id"], row["lab_id"], row["start_date"], row["end_date"], "有效", body.reference, now()))
        db.execute("UPDATE applications SET execution_status='已生效',execution_ref=?,execution_by=?,execution_at=?,version=version+1,updated_at=? WHERE id=?", (body.reference, p.id, now(), now(), app_id))
        event(db, app_id, p.id, "授权登记已核对", body.reference)
        notify(db, row["user_id"], "许可已登记", "许可已登记；准入仍需满足当前资质及实验室要求。门禁下发未接入。", app_id)
        return serialize(db, owned(db, app_id, p, True))


class Revoke(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


@router.post("/admin/permits/{grant_id}/revoke")
async def revoke(grant_id: str, body: Revoke, p: Principal = Depends(admin)):
    data = await snapshot()
    grant = next((a for a in data["authorizations"] if a["id"] == grant_id), None)
    if not grant or not p.can_lab(grant["labId"]):
        fail(404, "NOT_FOUND", "许可不存在或不在管理范围")
    with connection() as db:
        if get_settings().business_data_source == "application":
            data = json.loads(db.execute("SELECT payload FROM business_data WHERE id=1").fetchone()[0])
            grant = next(a for a in data["authorizations"] if a["id"] == grant_id)
            grant["status"] = "已撤销"
            save_snapshot(db, data)
        elif grant["status"] != "已撤销":
            fail(409, "REVOCATION_NOT_CONFIRMED", "请先在原授权渠道撤销，系统核对后再确认")
        db.execute("UPDATE permit_history SET status='已撤销' WHERE person_id=? AND lab_id=?", (grant["personId"], grant["labId"]))
        db.execute("UPDATE applications SET execution_status='已撤销',version=version+1,updated_at=? WHERE person_id=? AND lab_id=? AND execution_status='已生效'", (now(), grant["personId"], grant["labId"]))
        audit(db, p.id, "撤销许可", grant_id, {"note": body.note})
        user = db.execute("SELECT id FROM users WHERE person_id=?", (grant["personId"],)).fetchone()
        if user:
            notify(db, user[0], "许可已撤销", body.note)
    return {"ok": True}


class Attachment(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(max_length=2_800_000)


@router.post("/me/permit-applications/{app_id}/attachments")
def upload(app_id: str, body: Attachment, p: Principal = Depends(current)):
    try:
        content = base64.b64decode(body.content, validate=True)
    except (ValueError, binascii.Error):
        fail(422, "FILE_INVALID", "文件编码无效")
    if not content or len(content) > 2_000_000:
        fail(422, "FILE_TOO_LARGE", "文件大小需在 2 MB 以内")
    signatures = [(b"%PDF-", "application/pdf", ".pdf"), (b"\x89PNG\r\n\x1a\n", "image/png", ".png"), (b"\xff\xd8\xff", "image/jpeg", ".jpg")]
    match = next((x for x in signatures if content.startswith(x[0])), None)
    if not match or not body.name.lower().endswith((match[2], ".jpeg") if match[2] == ".jpg" else (match[2],)):
        fail(422, "FILE_TYPE_INVALID", "仅支持内容与扩展名一致的 PDF、PNG 和 JPEG 文件")
    with connection() as db:
        row = owned(db, app_id, p)
        if row["status"] not in {"草稿", "待补充"}:
            fail(409, "STATE_INVALID", "当前状态不允许补充材料")
        if db.execute("SELECT count(*) FROM attachments WHERE application_id=?", (app_id,)).fetchone()[0] >= 5:
            fail(422, "FILE_LIMIT", "每份申请最多 5 个附件")
        file_id = uuid.uuid4().hex
        db.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?)", (file_id, app_id, body.name, match[1], content, now()))
        db.execute("UPDATE applications SET version=version+1,updated_at=? WHERE id=?", (now(), app_id))
        event(db, app_id, p.id, "上传材料", body.name)
    return {"id": file_id}


@router.get("/attachments/{file_id}")
def download(file_id: str, p: Principal = Depends(current)):
    with connection() as db:
        file = db.execute("SELECT * FROM attachments WHERE id=?", (file_id,)).fetchone()
        if not file:
            fail(404, "NOT_FOUND", "附件不存在")
        row = db.execute("SELECT * FROM applications WHERE id=?", (file["application_id"],)).fetchone()
        if row["user_id"] != p.id and not p.can_lab(row["lab_id"]):
            fail(404, "NOT_FOUND", "附件不存在")
        audit(db, p.id, "下载材料", file_id)
        from urllib.parse import quote
        return Response(file["content"], media_type=file["media_type"], headers={"Content-Disposition": "attachment; filename*=UTF-8''"+quote(file["name"], safe=""), "X-Content-Type-Options": "nosniff"})


@router.get("/me/notifications")
def notifications(page: int = Query(1, ge=1), page_size: int = Query(30, ge=1, le=100), p: Principal = Depends(current)):
    with connection() as db:
        items = db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT ? OFFSET ?", (p.id, page_size, (page-1)*page_size))
        return {"items": [dict(r) for r in items], "total": db.execute("SELECT count(*) FROM notifications WHERE user_id=?", (p.id,)).fetchone()[0]}


@router.post("/me/notifications/{message_id}/read")
def read_notification(message_id: int, p: Principal = Depends(current)):
    with connection() as db:
        result = db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (message_id, p.id))
        if not result.rowcount:
            fail(404, "NOT_FOUND", "通知不存在")
    return {"ok": True}


@router.get("/admin/users")
def users(p: Principal = Depends(system_admin)):
    with connection() as db:
        return [dict(r) for r in db.execute("SELECT id,username,person_id,display_name,role,system_admin,lab_ids,active,must_change_password FROM users ORDER BY username")]


@router.get("/admin/unlinked-persons")
async def unlinked_persons(p: Principal = Depends(system_admin)):
    data = await snapshot()
    with connection() as db:
        linked = {r[0] for r in db.execute("SELECT person_id FROM users")}
    return [v for v in data["persons"] if v["id"] not in linked]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.@-]+$")
    personId: str = Field(min_length=1, max_length=64)


@router.post("/admin/users")
async def create_user(body: UserCreate, p: Principal = Depends(system_admin)):
    profile = person(await snapshot(), body.personId)
    password = secrets.token_urlsafe(15)
    with connection() as db:
        if db.execute("SELECT id FROM users WHERE username=? OR person_id=?", (body.username, body.personId)).fetchone():
            fail(409, "USER_EXISTS", "账号或人员已经绑定，不能重复创建")
        user_id = "usr-"+uuid.uuid4().hex[:12]
        db.execute("INSERT INTO users(id,username,password_hash,person_id,display_name,role) VALUES(?,?,?,?,?,'user')",
                   (user_id, body.username, hash_password(password), body.personId, profile["name"]))
        audit(db, p.id, "创建账号", user_id, {"personId": body.personId, "username": body.username})
    return {"id": user_id, "temporaryPassword": password}


class UserUpdate(BaseModel):
    active: bool
    role: str
    labIds: list[str] = Field(default_factory=list, max_length=100)


@router.patch("/admin/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, p: Principal = Depends(system_admin)):
    if user_id == p.id:
        fail(409, "SELF_CHANGE_DENIED", "不能在此修改本人角色或启停状态")
    if body.role not in {"admin", "user"}:
        fail(422, "ROLE_INVALID", "角色无效")
    data = await snapshot()
    if not set(body.labIds) <= {l["labId"] for l in data["labs"]}:
        fail(422, "LAB_INVALID", "实验室范围无效")
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            fail(404, "NOT_FOUND", "账号不存在")
        if row["system_admin"]:
            fail(409, "SYSTEM_ACCOUNT_PROTECTED", "系统管理账号由部署维护流程管理")
        db.execute("UPDATE users SET active=?,role=?,lab_ids=? WHERE id=?", (int(body.active), body.role, json.dumps(body.labIds if body.role=="admin" else []), user_id))
        db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        audit(db, p.id, "变更账号权限", user_id, body.model_dump())
    return {"ok": True}


@router.post("/admin/users/{user_id}/reset-password")
def reset_password(user_id: str, p: Principal = Depends(system_admin)):
    password = secrets.token_urlsafe(15)
    with connection() as db:
        if not db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone():
            fail(404, "NOT_FOUND", "账号不存在")
        db.execute("UPDATE users SET password_hash=?,must_change_password=1 WHERE id=?", (hash_password(password), user_id))
        db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        audit(db, p.id, "重置密码", user_id)
    return {"temporaryPassword": password, "message": "仅显示本次，请通过可信渠道交付；首次登录必须修改"}


@router.get("/admin/audit-events")
def audits(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), p: Principal = Depends(system_admin)):
    with connection() as db:
        return {"items": [dict(r) for r in db.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT ? OFFSET ?", (page_size, (page-1)*page_size))],
                "total": db.execute("SELECT count(*) FROM audit_events").fetchone()[0]}


@router.get("/me/access-check")
async def access_check(lab_id: str, p: Principal = Depends(current)):
    data = await snapshot()
    person(data, p.person_id)
    issues = qualification_issues(data, p.person_id, lab_id)
    grant = next((a for a in data["authorizations"] if a["personId"]==p.person_id and a["labId"]==lab_id), None)
    if not grant or permit_status(data, grant) != "有效":
        issues.append("当前没有有效的实验室许可")
    lab = next((l for l in data["labs"] if l["labId"]==lab_id), None)
    if lab and lab["needsDouble"]:
        issues.append("需要双人准入，当前未接入可核验的实时同行证据")
    return {"allowed": not issues, "issues": issues, "checkedAt": now(), "hardwareStatus": "门禁下发未接入"}
