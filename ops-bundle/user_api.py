from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.schemas.user_schema import RegisterSchema, LoginSchema
from app.service.user_service import user_register, user_login, check_user_auth
from app.common.response import success, fail
from app.common.security import parse_token
from app.common.limiter import limiter


def check_password_strength(password: str) -> tuple:
    """密码强度校验: 至少8位，包含字母和数字"""
    if len(password) < 8:
        return False, "密码至少8位"
    if not any(c.isalpha() for c in password):
        return False, "密码必须包含字母"
    if not any(c.isdigit() for c in password):
        return False, "密码必须包含数字"
    return True, ""

router = APIRouter()

@router.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, data: RegisterSchema, db: Session = Depends(get_db)):
    ok, msg = user_register(db, data.username, data.password)
    if not ok:
        return fail(msg=msg)
    return success(msg=msg)

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, data: LoginSchema, db: Session = Depends(get_db)):
    ok, res = user_login(db, data.username, data.password)
    if not ok:
        return fail(msg=res)
    return success(data=res)

@router.get("/auth")
async def auth(token: str, db: Session = Depends(get_db)):
    payload = parse_token(token)
    if not payload:
        return fail(code=401, msg="登录已过期，请重新登录")
    user_id = payload.get("user_id")
    ok, msg = check_user_auth(db, user_id)
    if not ok:
        return fail(code=401, msg=msg)
    return success(msg="权限正常")

@router.post("/logout")
async def logout():
    return success(msg="退出成功")
