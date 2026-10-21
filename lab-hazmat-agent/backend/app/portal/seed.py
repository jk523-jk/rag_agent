"""python -m app.portal.seed --apply；默认只预览。生成凭证写入忽略的本地文件。"""
from __future__ import annotations

import argparse
import json
import random
import secrets
import uuid
from datetime import date, timedelta
from pathlib import Path

from app.core.config import get_settings
from app.portal.auth import hash_password
from app.portal.business import COLLECTIONS, save_snapshot
from app.portal.store import audit, connection, event, notify, now


def generate(base: date, seed: int = 20261021) -> dict:
    rng = random.Random(seed)
    day = lambda n: (base + timedelta(days=n)).isoformat()
    groups = ["化学学院", "材料学院", "生命科学学院", "物理学院", "分析测试中心", "环境学院"]
    names = ["陈知远", "林若溪", "周明哲", "许清禾", "李明", "李明", "沈亦宁", "赵思齐", "吴书衡", "苏予安"]
    persons = [{"id": str(i), "name": names[(i-1) % len(names)] + (str((i-1)//10+1) if i > 10 else ""),
                "empNo": f"U{20260000+i}", "dept": groups[(i-1) % 6], "role": "教师" if i <= 4 else ("硕士生" if i % 3 else "博士生")}
               for i in range(1, 121)]
    labs = [{"labId": f"LAB-{i:02}", "labName": f"{['合成化学', '材料表征', '生命分析', '物理测试', '分析检测', '环境分析'][(i-1)%6]}实验室{i}",
             "hazmatClass": "易燃液体" if i % 2 else "一般化学品", "needsDouble": i in (3, 9),
             "mgrName": persons[(i-1)%3+1]["name"], "status": "暂停开放" if i == 12 else "开放",
             "requiredCerts": ["安全考试合格证", "危化品操作证"] if i % 2 else ["安全考试合格证"]}
            for i in range(1, 13)]
    qualifications = [{"id": f"q-{p['id']}-{j}", "personId": p["id"], "certType": cert,
                       "certNo": f"CERT-{p['empNo']}-{j}", "issueDate": day(-150),
                       "expireDate": day(-7 if int(p["id"]) % 17 == 0 else 7 if int(p["id"]) % 13 == 0 else 365),
                       "status": "已注销" if int(p["id"]) % 29 == 0 else "有效"}
                      for p in persons for j, cert in enumerate(["安全考试合格证", "危化品操作证"])]
    auths = []
    for i in range(180):
        pid = str(i % 120 + 1)
        lid = f"LAB-{(i % 120)//10+1:02}"
        if i >= 120:
            lid = f"LAB-{((i%120)//10+1)%12+1:02}"
        auths.append({"id": f"a-{pid}-{lid}", "personId": pid, "labId": lid,
                      "authFrom": day(-100), "authTo": day(-3 if i % 11 == 0 else 30 if i % 7 == 0 else 180),
                      "grantor": persons[1]["name"], "status": "已撤销" if i % 23 == 0 else "有效"})
    equipment = [{"id": f"EQ-{i:03}", "equipId": f"EQ-{i:03}", "equipName": ["电子天平", "离心机", "分光光度计", "恒温培养箱", "磁力搅拌器"][(i-1)%5]+str(i),
                  "category": "分析仪器", "modelNo": f"LAB-{i:03}", "labId": f"LAB-{(i-1)%12+1:02}",
                  "keeperId": str((i-1)%3+2), "status": "维修中" if i % 19 == 0 else "在用",
                  "calibrateDue": day(-2 if i % 9 == 0 else 150), "purchaseDate": day(-700), "remark": "定期检查并按规程操作"}
                 for i in range(1, 61)]
    loans = []
    for i in range(160):
        loans.append({"id": f"l-{i+1}", "equipId": equipment[i%60]["id"], "personId": str(i%116+5),
                      "borrowTime": day(-170+i)+" 09:00", "dueTime": day(-168+i)+" 17:00",
                      "returnTime": day(-169+i)+" 15:00", "purpose": "课题实验测量", "approver": persons[1]["name"], "status": "已归还"})
    # Only final loans for different equipment remain outstanding.
    for i, loan in enumerate(loans[-12:]):
        loan.update(borrowTime=day(-5)+" 09:00", dueTime=day(-1 if i%3 == 0 else 3)+" 17:00", returnTime=None, status="逾期" if i%3 == 0 else "借用中")
    inventory = [{"id": str(i), "chemName": ["乙醇", "氯化钠", "乙酸", "丙酮", "碳酸钠"][(i-1)%5],
                  "casNo": ["64-17-5", "7647-14-5", "64-19-7", "67-64-1", "497-19-8"][(i-1)%5],
                  "hazardClass": "易燃液体" if i % 5 in (1,4) else "一般化学品",
                  "labId": f"LAB-{(i-1)%12+1:02}", "cabinetNo": f"CAB-{i:03}", "quantity": 100.0,
                  "openingQuantity": 130.0, "unit": "克", "updatedAt": day(0)+" 08:00"} for i in range(1, 101)]
    uses = [{"id": f"u-{i+1}", "itemId": str(i%100+1), "personId": str(i%116+5),
             "useTime": day(-90+(i//100)*30), "quantity": 10.0, "witnessId": None, "purpose": "课题分析测试"} for i in range(300)]
    events = []
    # Build events from grants valid at event time, rather than independently picking people/labs.
    for i in range(1500):
        grant = auths[rng.randrange(len(auths))]
        age = rng.randrange(1, 90)
        when = day(-age)
        permitted = grant["status"] == "有效" and grant["authFrom"] <= when <= grant["authTo"]
        certs = [q for q in qualifications if q["personId"] == grant["personId"]]
        permitted = permitted and all(q["status"] == "有效" and q["issueDate"] <= when <= q["expireDate"] for q in certs)
        lab = next(l for l in labs if l["labId"] == grant["labId"])
        permitted = permitted and lab["status"] == "开放"
        for j, (direction, hour) in enumerate((("进", "09:00"), ("出", "11:00"))):
            events.append({"id": f"e-{i*2+j+1}", "personId": grant["personId"], "labId": grant["labId"],
                           "eventTime": f"{when} {hour}", "direction": direction, "authType": "工卡",
                           "authResult": "通过" if permitted else "拒绝", "companionNo": 2 if lab["needsDouble"] else 1})
    data = dict(zip(COLLECTIONS, [labs, persons, qualifications, auths, events, inventory, uses, equipment, loans]))
    validate(data)
    return data


def validate(data: dict):
    people = {p["id"] for p in data["persons"]}
    labs = {p["labId"] for p in data["labs"]}
    equipment = {p["equipId"] for p in data["equipment"]}
    inventory = {p["id"] for p in data["inventory"]}
    assert len(people) == len(data["persons"])
    assert len({p["empNo"] for p in data["persons"]}) == len(people)
    assert len({(a["personId"], a["labId"]) for a in data["authorizations"]}) == len(data["authorizations"])
    for key in COLLECTIONS:
        for row in data[key]:
            if "personId" in row:
                assert row["personId"] in people, (key, row)
            if "labId" in row:
                assert row["labId"] in labs
            if "equipId" in row and key != "equipment":
                assert row["equipId"] in equipment
            if "itemId" in row:
                assert row["itemId"] in inventory
    for row in data["qualifications"]:
        assert row["issueDate"] <= row["expireDate"]
    for row in data["equipmentLoans"]:
        assert row["borrowTime"] <= row["dueTime"]
        assert row["returnTime"] is None or row["borrowTime"] <= row["returnTime"]
    for item in data["inventory"]:
        assert item["openingQuantity"] - sum(u["quantity"] for u in data["hazmatUses"] if u["itemId"] == item["id"]) == item["quantity"]


def initialize(base: date, seed: int = 20261021, credential_path: Path | None = None) -> dict:
    with connection() as db:
        if db.execute("SELECT count(*) FROM users").fetchone()[0] or db.execute("SELECT 1 FROM business_data").fetchone():
            return {"initialized": False, "message": "已有初始化数据或账号，已跳过；未覆盖已有数据及凭证"}
    data = generate(base, seed)
    credentials = []
    # Hashing happens outside the transaction; new passwords are unique and never logged.
    for i, person in enumerate(data["persons"]):
        password = secrets.token_urlsafe(15)
        credentials.append({"username": "admin" if i == 0 else f"manager{i}" if i < 4 else person["empNo"],
                            "password": password, "personId": person["id"], "name": person["name"],
                            "role": "admin" if i < 4 else "user", "hash": hash_password(password)})
    path = credential_path or get_settings().application_db.parent / "initial-credentials.local.json"
    # Never overwrite credentials for an existing initialized system.
    with connection() as db:
        if db.execute("SELECT count(*) FROM users").fetchone()[0] or db.execute("SELECT 1 FROM business_data").fetchone():
            return {"initialized": False, "message": "已有初始化数据或账号，已跳过；未覆盖已有数据及凭证"}
        if path.exists():
            raise RuntimeError("凭证目标文件已存在，请使用新的 --credentials 路径")
        save_snapshot(db, data)
        for grant in data["authorizations"]:
            db.execute("INSERT INTO permit_history VALUES(?,NULL,?,?,?,?,?,?,?)", ("initial-"+grant["id"], grant["personId"], grant["labId"], grant["authFrom"], grant["authTo"], grant["status"], "initial-v1", now()))
        for i, c in enumerate(credentials):
            scope = [l["labId"] for j, l in enumerate(data["labs"]) if j%3 == i-1] if 0 < i < 4 else []
            db.execute("INSERT INTO users(id,username,password_hash,person_id,display_name,role,system_admin,lab_ids) VALUES(?,?,?,?,?,?,?,?)",
                       (f"usr-{i+1}", c["username"], c["hash"], c["personId"], c["name"], c["role"], int(i==0), json.dumps(scope)))
        states = ["待审批", "待补充", "已驳回", "已撤回", "草稿", "已通过", "已通过", "已失效"]
        for i in range(80):
            uid, pid = f"usr-{i+5}", str(i+5)
            app_id, lid = f"REQ-INIT-{i+1:04}", f"LAB-{i%11+1:02}"
            status = states[i%len(states)]
            execution = "未执行"
            if status == "已通过":
                valid = all(q["status"]=="有效" and q["expireDate"] >= (base+timedelta(days=30)).isoformat() for q in data["qualifications"] if q["personId"]==pid)
                if not valid:
                    status = "已驳回"
                else:
                    execution = "待生效" if i%len(states)==5 else "已生效"
            created = (base-timedelta(days=10)).isoformat()+"T09:00:00+08:00"
            db.execute("INSERT INTO applications(id,user_id,person_id,lab_id,kind,purpose,start_date,end_date,status,created_at,updated_at,submitted_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (app_id, uid, pid, lid, "新申请", "课题实验准入", base.isoformat(), (base+timedelta(days=30)).isoformat(), status, created, created, created if status!="草稿" else None))
            event(db, app_id, uid, "创建申请", "初始化历史申请")
            if status != "草稿":
                event(db, app_id, uid, "提交申请")
            if status in {"待补充", "已驳回"}:
                event(db, app_id, "usr-1", status, "请提供与实验内容相符的用途说明及资质材料")
                db.execute("UPDATE applications SET reviewer_id='usr-1' WHERE id=?", (app_id,))
            elif status == "已撤回":
                event(db, app_id, uid, "撤回申请", "实验计划调整")
            elif status == "已失效":
                db.execute("UPDATE applications SET start_date=?,end_date=? WHERE id=?", ((base-timedelta(days=7)).isoformat(), (base-timedelta(days=1)).isoformat(), app_id))
                event(db, app_id, "system", "申请失效", "超过申请结束日期")
            elif status == "已通过":
                db.execute("UPDATE applications SET reviewer_id='usr-1',execution_status=? WHERE id=?", (execution, app_id))
                event(db, app_id, "usr-1", "审批通过", "申请资料与资质已核对")
                if execution == "已生效":
                    reference = "REG-INIT-"+str(i+1)
                    grant = next((a for a in data["authorizations"] if a["personId"]==pid and a["labId"]==lid), None)
                    if not grant:
                        # Keep target grant count stable: replace this person's secondary grant.
                        grant = next(a for a in data["authorizations"] if a["personId"]==pid)
                    grant.update(id=f"a-{pid}-{lid}", labId=lid, authFrom=base.isoformat(), authTo=(base+timedelta(days=30)).isoformat(), status="有效", grantor=data["persons"][0]["name"])
                    db.execute("UPDATE applications SET execution_ref=?,execution_by='usr-1',execution_at=? WHERE id=?", (reference,now(),app_id))
                    db.execute("INSERT INTO permit_history VALUES(?,?,?,?,?,?,?,?,?)", ("permit-"+app_id,app_id,pid,lid,base.isoformat(),(base+timedelta(days=30)).isoformat(),"有效",reference,now()))
                    event(db, app_id, "usr-1", "授权登记已核对", reference)
            notify(db, uid, "申请进度", f"申请 {app_id} 当前状态：{status}", app_id)
        validate(data)
        save_snapshot(db, data)
        batch = {"source": "generated", "baseDate": base.isoformat(), "seed": seed, "version": 1,
                 "counts": {k: len(v) for k, v in data.items()}}
        db.execute("INSERT INTO seed_batches VALUES(?,?,?)", ("initial-v1", now(), json.dumps(batch, ensure_ascii=False)))
        audit(db, "initializer", "初始化", "initial-v1", batch)
        # Exclusive creation prevents accidental overwrites; no credentials in stdout.
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as output:
            json.dump([{k: v for k, v in c.items() if k != "hash"} for c in credentials], output, ensure_ascii=False, indent=2)
    return {"initialized": True, "credentialsFile": str(path), **batch}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="显式写入空应用库；重复执行不覆盖")
    parser.add_argument("--base-date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--seed", type=int, default=20261021)
    parser.add_argument("--credentials", type=Path)
    args = parser.parse_args()
    result = initialize(args.base_date, args.seed, args.credentials) if args.apply else {"preview": True, "counts": {k: len(v) for k,v in generate(args.base_date,args.seed).items()}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
