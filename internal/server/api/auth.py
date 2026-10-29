import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from internal.server.dependencies import ServerContext
from internal.server.schemas import Login
from internal.server.security import token_hash, verify_password


def build_router(context: ServerContext) -> APIRouter:
    router = APIRouter()
    database = context.database
    config = context.config
    session = context.session
    attempts: dict[str, deque] = defaultdict(deque)
    attempts_lock = threading.Lock()

    @router.post("/api/auth/login")
    def login(payload: Login, request: Request, response: Response):
        if request.headers.get("origin") not in {None, config.public_url}:
            raise HTTPException(403, "请求来源无效")
        address = request.client.host if request.client else "unknown"
        now = time.time()
        with attempts_lock:
            if len(attempts) > 1024:
                attempts.clear()
            history = attempts[address]
            while history and history[0] < now - 60:
                history.popleft()
            if len(history) >= 10:
                raise HTTPException(429, "登录尝试过多，请稍后重试")
            history.append(now)
        with database.read() as conn:
            admin = conn.execute("SELECT * FROM admin WHERE id=1").fetchone()
        valid_password = verify_password(
            payload.password.get_secret_value(), admin["password_hash"]
        )
        if payload.username != admin["username"] or not valid_password:
            raise HTTPException(401, "用户名或密码错误")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with database.transaction() as conn:
            conn.execute(
                "INSERT INTO sessions VALUES(?,?,?)",
                (token_hash(token), csrf, now + config.session_seconds),
            )
        response.set_cookie(
            "geo_session",
            token,
            max_age=config.session_seconds,
            secure=config.cookie_secure,
            httponly=True,
            samesite="strict",
            path="/",
        )
        return {"username": config.admin_username, "csrf_token": csrf}

    @router.get("/api/auth/me")
    def me(current: Annotated[dict, Depends(session)]):
        return {"username": config.admin_username, "csrf_token": current["csrf_token"]}

    @router.post("/api/auth/logout")
    def logout(response: Response, current: Annotated[dict, Depends(session)]):
        with database.transaction() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (current["token_hash"],))
        response.delete_cookie("geo_session", path="/")
        return {"ok": True}

    return router
