"""独立应用存储；所有审批状态变更在 BEGIN IMMEDIATE 事务中执行。"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

from app.core.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 person_id TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL, role TEXT NOT NULL,
 system_admin INTEGER NOT NULL DEFAULT 0, lab_ids TEXT NOT NULL DEFAULT '[]',
 active INTEGER NOT NULL DEFAULT 1, must_change_password INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 csrf TEXT NOT NULL, created_at REAL NOT NULL, last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
 key TEXT PRIMARY KEY, failures INTEGER NOT NULL, window_start REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS business_data (
 id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seed_batches (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS applications (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), person_id TEXT NOT NULL,
 lab_id TEXT NOT NULL, kind TEXT NOT NULL, purpose TEXT NOT NULL,
 start_date TEXT NOT NULL, end_date TEXT NOT NULL, status TEXT NOT NULL,
 execution_status TEXT NOT NULL DEFAULT '未执行', version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, submitted_at TEXT,
 reviewer_id TEXT, evidence_snapshot TEXT NOT NULL DEFAULT '{}',
 execution_ref TEXT NOT NULL DEFAULT '', execution_by TEXT, execution_at TEXT
);
CREATE INDEX IF NOT EXISTS applications_user ON applications(user_id, updated_at);
CREATE INDEX IF NOT EXISTS applications_lab ON applications(lab_id, status);
CREATE TABLE IF NOT EXISTS application_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, application_id TEXT NOT NULL REFERENCES applications(id),
 actor_id TEXT NOT NULL, action TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attachments (
 id TEXT PRIMARY KEY, application_id TEXT NOT NULL REFERENCES applications(id),
 name TEXT NOT NULL, media_type TEXT NOT NULL, content BLOB NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS permit_history (
 id TEXT PRIMARY KEY, application_id TEXT UNIQUE REFERENCES applications(id), person_id TEXT NOT NULL,
 lab_id TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
 status TEXT NOT NULL, source_ref TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, body TEXT NOT NULL, application_id TEXT,
 dedupe_key TEXT UNIQUE, is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL, action TEXT NOT NULL,
 target TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def today() -> str:
    return now()[:10]


@contextmanager
def connection():
    path = get_settings().application_db
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def audit(db, actor: str, action: str, target: str, detail: dict | None = None):
    db.execute("INSERT INTO audit_events(actor_id,action,target,detail,created_at) VALUES(?,?,?,?,?)",
               (actor, action, target, json.dumps(detail or {}, ensure_ascii=False), now()))


def notify(db, user_id: str, title: str, body: str, application_id: str | None = None,
           dedupe_key: str | None = None):
    db.execute("INSERT OR IGNORE INTO notifications(user_id,title,body,application_id,dedupe_key,created_at) "
               "VALUES(?,?,?,?,?,?)", (user_id, title, body, application_id, dedupe_key, now()))


def event(db, application_id: str, actor: str, action: str, note: str = ""):
    db.execute("INSERT INTO application_events(application_id,actor_id,action,note,created_at) VALUES(?,?,?,?,?)",
               (application_id, actor, action, note, now()))
    audit(db, actor, action, application_id, {"note": note})
