#!/usr/bin/env python3
"""admin_api.py — 管理后台API"""
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.common.response import success, fail
from app.common.security import parse_token

router = APIRouter()


def require_admin(request: Request):
    """管理员认证 — 需要 role=admin 的JWT"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    payload = parse_token(token)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="无权限")
    return payload


@router.get("/users")
async def admin_list_users(request: Request, db: Session = Depends(get_db)):
    """用户列表"""
    require_admin(request)
    from app.crud.user_crud import get_all_users
    users = get_all_users(db)
    return success(data=[{
        "id": u.id,
        "username": u.username,
        "vip_type": u.vip_type,
        "status": u.status,
        "created_at": str(u.created_at) if u.created_at else None,
    } for u in users])


@router.get("/orders")
async def admin_list_orders(request: Request, db: Session = Depends(get_db)):
    """订单列表"""
    require_admin(request)
    from app.crud.order_crud import get_all_orders
    orders = get_all_orders(db)
    return success(data=[{
        "order_sn": o.order_sn,
        "amount": float(o.amount),
        "status": o.status,
        "created_at": str(o.created_at) if o.created_at else None,
    } for o in orders])


@router.get("/apps")
async def admin_list_apps(request: Request, db: Session = Depends(get_db)):
    """软件列表"""
    require_admin(request)
    from app.crud.app_crud import get_all_apps
    apps = get_all_apps(db)
    return success(data=[{
        "app_id": a.app_id,
        "app_name": a.app_name,
        "status": a.status,
        "created_at": str(a.created_at) if a.created_at else None,
    } for a in apps])
