"""供既有只读工具/巡检使用的隔离业务快照；库中不包含账号或会话表。"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import date, datetime

import sqlglot
from sqlglot import exp

from app.core.config import get_settings
from app.portal.store import connection, today

TABLES = {
    "labs": ("labs", "labId:lab_id labName:lab_name hazmatClass:hazmat_class needsDouble:needs_double mgrName:mgr_name status:status"),
    "persons": ("persons", "id:id name:name empNo:emp_no dept:dept role:role"),
    "qualifications": ("qualifications", "personId:person_id certType:cert_type certNo:cert_no issueDate:issue_date expireDate:expire_date status:status"),
    "lab_authorizations": ("authorizations", "personId:person_id labId:lab_id authFrom:auth_from authTo:auth_to grantor:grantor status:status"),
    "access_events": ("accessEvents", "id:id personId:person_id labId:lab_id eventTime:event_time direction:direction authType:auth_type authResult:auth_result companionNo:companion_no"),
    "hazmat_inventory": ("inventory", "id:item_id chemName:chem_name casNo:cas_no hazardClass:hazard_class labId:lab_id cabinetNo:cabinet_no quantity:quantity unit:unit updatedAt:updated_at"),
    "hazmat_uses": ("hazmatUses", "id:id itemId:item_id personId:person_id useTime:use_time quantity:quantity witnessId:witness_id purpose:purpose"),
    "equipment": ("equipment", "equipId:equip_id equipName:equip_name category:category modelNo:model_no labId:lab_id keeperId:keeper_id status:status calibrateDue:calibrate_due purchaseDate:purchase_date remark:remark"),
    "equipment_loans": ("equipmentLoans", "id:id equipId:equip_id personId:person_id borrowTime:borrow_time dueTime:due_time returnTime:return_time purpose:purpose approver:approver status:status"),
}


def available() -> bool:
    with connection() as db:
        return bool(db.execute("SELECT 1 FROM business_data WHERE id=1").fetchone())


def query(sql: str, params: dict | None = None) -> list[dict]:
    with connection() as db:
        row = db.execute("SELECT payload FROM business_data WHERE id=1").fetchone()
    if not row:
        raise RuntimeError("业务数据尚未初始化")
    data = json.loads(row[0])
    # Only business data is materialized, even a model-generated SELECT cannot reach auth tables.
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    try:
        for table, (key, mapping) in TABLES.items():
            columns = [pair.split(":") for pair in mapping.split()]
            db.execute(f"CREATE TABLE {table} ({','.join(col+' '+('REAL' if col in {'quantity','needs_double','companion_no'} else 'TEXT') for _,col in columns)})")
            db.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in columns)})", [tuple(item.get(field) for field,_ in columns) for item in data[key]])
        db.commit()
        # Preserve bound parameters through MySQL -> SQLite expression translation.
        translated = re.sub(r"%\((\w+)\)s", r"@\1", sql)
        tree = sqlglot.parse_one(translated, read="mysql")
        def dates(node):
            if isinstance(node, (exp.DateSub, exp.DateAdd)):
                left, count, unit = node.this, node.expression, node.args.get("unit")
                sign = "-" if isinstance(node, exp.DateSub) else "+"
            elif isinstance(node, (exp.Add, exp.Sub)) and isinstance(node.expression, exp.Interval):
                left, count, unit = node.this, node.expression.this, node.expression.args.get("unit")
                sign = "-" if isinstance(node, exp.Sub) else "+"
            else:
                return node
            unit_name = (unit.name if unit else "DAY").lower()
            if unit_name not in {"day", "month", "year", "hour", "minute", "second"}:
                raise ValueError("不支持的日期间隔单位")
            return sqlglot.parse_one(f"DATETIME({left.sql(dialect='sqlite')}, '{sign}' || CAST({count.sql(dialect='sqlite')} AS TEXT) || ' {unit_name}')", read="sqlite")
        translated = tree.transform(dates).sql(dialect="sqlite")
        db.create_function("CURRENT_DATE_LOCAL", 0, today)
        # SQLite's CURRENT_DATE is UTC; use the same service date as permit checks.
        translated = re.sub(r"\bCURRENT_DATE\b(?:\(\))?", "CURRENT_DATE_LOCAL()", translated, flags=re.I)
        deadline = time.monotonic() + get_settings().sql_timeout_ms / 1000
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        db.execute("PRAGMA query_only=ON")
        result = [dict(r) for r in db.execute(translated, params or {})]
        # Match aiomysql's DATE / DATETIME return types for existing tool predicates.
        for row in result:
            for key, value in row.items():
                if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    row[key] = date.fromisoformat(value)
                elif isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?", value):
                    row[key] = datetime.fromisoformat(value)
        return result
    finally:
        db.close()
