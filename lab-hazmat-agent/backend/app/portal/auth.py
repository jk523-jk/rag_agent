from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.portal.store import audit, connection

COOKIE = "lab_session"
router = APIRouter(prefix="/auth", tags=["auth"])


def fail(status: int, code: str, message: str):
    raise HTTPException(status, detail={"code": code, "message": message})


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000).hex()
    return f"pbkdf2_sha256$310000${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


@dataclass
class Principal:
    id: str
    username: str
    person_id: str
    display_name: str
    role: str
    system_admin: bool
    lab_ids: list[str]
    must_change_password: bool
    csrf: str

    def public(self):
        return {"id": self.id, "username": self.username, "personId": self.person_id,
                "displayName": self.display_name, "role": self.role,
                "systemAdmin": self.system_admin, "labIds": self.lab_ids,
                "mustChangePassword": self.must_change_password, "csrfToken": self.csrf}

    def can_lab(self, lab_id: str) -> bool:
        return self.role == "admin" and (self.system_admin or lab_id in self.lab_ids)


def current(request: Request) -> Principal:
    cached = getattr(request.state, "principal", None)
    if cached:
        return cached
    token = request.cookies.get(COOKIE, "")
    digest = hashlib.sha256(token.encode()).hexdigest()
    s = get_settings()
    with connection() as db:
        row = db.execute("SELECT u.*,s.csrf,s.created_at,s.last_seen FROM sessions s JOIN users u "
                         "ON u.id=s.user_id WHERE s.token_hash=?", (digest,)).fetchone()
        timestamp = time.time()
        if not row or not row["active"] or timestamp - row["last_seen"] > s.auth_idle_seconds or timestamp - row["created_at"] > s.auth_max_seconds:
            # Expired sessions never authenticate; purge on the next successful login.
            fail(401, "AUTH_REQUIRED", "登录已失效，请重新登录")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), row["csrf"]):
                fail(403, "CSRF_INVALID", "安全验证失败，请刷新页面后重试")
        if row["must_change_password"] and request.url.path not in {"/api/auth/me", "/api/auth/change-password", "/api/auth/logout"}:
            fail(403, "PASSWORD_CHANGE_REQUIRED", "首次登录请先修改密码")
        db.execute("UPDATE sessions SET last_seen=? WHERE token_hash=?", (timestamp, digest))
        p = Principal(row["id"], row["username"], row["person_id"], row["display_name"], row["role"],
                      bool(row["system_admin"]), json.loads(row["lab_ids"]), bool(row["must_change_password"]), row["csrf"])
    request.state.principal = p
    return p


def admin(p: Principal = Depends(current)) -> Principal:
    if p.role != "admin":
        fail(403, "PERMISSION_DENIED", "需要管理员权限")
    return p


def system_admin(p: Principal = Depends(admin)) -> Principal:
    if not p.system_admin:
        fail(403, "PERMISSION_DENIED", "需要系统管理权限")
    return p


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
def login(body: Login, request: Request, response: Response):
    # Same-origin login; additionally reject cross-site browser submissions.
    origin = request.headers.get("origin")
    if origin and request.headers.get("sec-fetch-site") != "same-origin" and origin not in get_settings().cors_origin_list and origin != f"{request.url.scheme}://{request.headers.get('host')}":
        fail(403, "ORIGIN_DENIED", "登录来源不允许")
    key = hashlib.sha256(f"{request.client.host if request.client else ''}|{body.username}".encode()).hexdigest()
    timestamp = time.time()
    failure = False
    with connection() as db:
        attempt = db.execute("SELECT * FROM login_attempts WHERE key=?", (key,)).fetchone()
        if attempt and timestamp - attempt["window_start"] < 900 and attempt["failures"] >= 8:
            fail(429, "LOGIN_LIMITED", "尝试次数过多，请 15 分钟后重试")
        user = db.execute("SELECT * FROM users WHERE username=?", (body.username.strip(),)).fetchone()
        # Fixed dummy PBKDF2 work avoids fast account enumeration.
        encoded = user["password_hash"] if user else "pbkdf2_sha256$310000$missing$" + "0" * 64
        verified = verify_password(body.password, encoded)
        if not user or not verified or not user["active"]:
            start = attempt["window_start"] if attempt and timestamp - attempt["window_start"] < 900 else timestamp
            count = attempt["failures"] + 1 if start != timestamp else 1
            db.execute("INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)", (key, count, start))
            audit(db, "anonymous", "登录失败", key)
            failure = True
        else:
            db.execute("DELETE FROM login_attempts WHERE key=?", (key,))
            db.execute("DELETE FROM sessions WHERE last_seen<? OR created_at<?", (timestamp-get_settings().auth_idle_seconds, timestamp-get_settings().auth_max_seconds))
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            db.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), user["id"], csrf, timestamp, timestamp))
            audit(db, user["id"], "登录", user["id"])
    if failure:
        fail(401, "LOGIN_FAILED", "账号或密码错误，或账号已停用")
    response.set_cookie(COOKIE, token, httponly=True, secure=get_settings().auth_cookie_secure,
                        samesite="lax", max_age=get_settings().auth_max_seconds, path="/api")
    return {"ok": True}


@router.get("/me")
def me(p: Principal = Depends(current)):
    return p.public()


@router.post("/logout")
def logout(request: Request, response: Response, p: Principal = Depends(current)):
    with connection() as db:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest(),))
        audit(db, p.id, "退出登录", p.id)
    response.delete_cookie(COOKIE, path="/api")
    return {"ok": True}


class PasswordChange(BaseModel):
    oldPassword: str = Field(min_length=1, max_length=128)
    newPassword: str = Field(min_length=10, max_length=128)


@router.post("/change-password")
def change_password(body: PasswordChange, response: Response, p: Principal = Depends(current)):
    if body.oldPassword == body.newPassword:
        fail(422, "PASSWORD_UNCHANGED", "新密码不能与原密码相同")
    with connection() as db:
        row = db.execute("SELECT password_hash FROM users WHERE id=?", (p.id,)).fetchone()
        if not verify_password(body.oldPassword, row[0]):
            fail(400, "PASSWORD_INVALID", "原密码不正确")
        db.execute("UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?", (hash_password(body.newPassword), p.id))
        db.execute("DELETE FROM sessions WHERE user_id=?", (p.id,))
        audit(db, p.id, "修改密码", p.id)
    response.delete_cookie(COOKIE, path="/api")
    return {"ok": True, "message": "密码已更新，请重新登录"}
