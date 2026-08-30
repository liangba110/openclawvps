from fastapi import APIRouter, Depends, Request

def get_token_from_header(request: Request) -> str:
    """从Authorization头获取token"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""

"""
多软件支付授权平台 - 软件侧 API
接口签名: sign = md5(app_id + params_sorted + app_key + timestamp)
"""
import hashlib, random, time, urllib.request, json as _json

from sqlalchemy.orm import Session
from app.db.base import get_db
from app.crud.app_crud import (get_app_by_id, create_app, get_app_user, create_app_user,
                               get_app_user_by_id, update_app_user_vip, create_app_order,
                               get_app_order_by_sn, update_app_order_paid,
                               mark_app_order_notified, list_app_orders)
from app.common.response import success, fail
from app.common.security import create_token, parse_token
from urllib.parse import urlparse
import shlex as _shlex
from app.config.logger import logger
from datetime import datetime, timedelta

router = APIRouter()

GOODS_PRICE = {1: 9.9, 2: 29.9, 3: 199.9, 4: 520.0}
GOODS_DAYS = {1: 1, 2: 30, 3: 365, 4: None}  # None=永久


def _app_price(app, goods_type: int) -> float:
    """取软件自定义价格，未设置则用全局默认"""
    v = getattr(app, f'price_{goods_type}', None)
    if v is not None and float(v) > 0:
        return float(v)
    return GOODS_PRICE.get(goods_type, 0)


def _md5(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def verify_sign(app_key: str, params: dict, sign: str, timestamp: str) -> bool:
    """验签: sign = md5(app_id + sorted_params + app_key + timestamp)"""
    try:
        if abs(int(timestamp) - int(time.time())) > 300:
            return False  # 5分钟时效
    except (ValueError, TypeError):
        return False
    keys = sorted([k for k in params if k not in ('sign', 'timestamp')])
    raw = params.get('app_id', '') + ''.join(f"{k}{params[k]}" for k in keys) + app_key + timestamp
    return _md5(raw) == sign


def require_app(app_id: str, db: Session):
    app = get_app_by_id(db, app_id)
    if not app or app.status != 1:
        return None
    return app


def _create_native_pay(order_sn: str, amount: float) -> str:
    """调统一支付网关 Native 扫码"""
    payload = _json.dumps({
        "out_trade_no": order_sn,
        "amount": amount,
        "subject": "广告信息展示服务"
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:5005/api/v1/wxpay/native",
        data=payload, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = _json.loads(resp.read().decode())
        if data.get("code") == 0 and data.get("data", {}).get("code_url"):
            return data["data"]["code_url"]
        logger.error(f"网关下单失败: {data}")
        return f"pay_error_{order_sn}"
    except Exception as e:
        logger.error(f"调用支付网关异常: {e}")
        return f"pay_error_{order_sn}"


# ============ 软件信息（公开，收银台用）============
@router.get("/info")
async def app_info(app_id: str, db: Session = Depends(get_db)):
    app = require_app(app_id, db)
    if not app:
        return fail(code=404, msg="软件不存在")
    return success(data={"app_id": app.app_id, "app_name": app.app_name, "logo_url": app.logo_url})


# ============ 网页收银台免签名接口（官方页面专用）============
@router.post("/page/login")
async def app_page_login(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    app_id = body.get('app_id', '')
    username = (body.get('username') or '').strip()
    password = body.get('password', '')
    app = require_app(app_id, db)
    if not app:
        return fail(code=401, msg="软件无效或已禁用")
    user = get_app_user(db, app_id, username)
    if not user:
        return fail(code=401, msg="用户名或密码错误")
    from app.common.security import verify_password
    if not verify_password(password, user.password):
        return fail(code=401, msg="用户名或密码错误")
    if user.status != 1:
        return fail(code=403, msg="账号已封禁")
    user.last_login_time = datetime.now()
    db.commit()
    token = create_token(user_id=user.id, username=user.username, app_id=app_id)
    return success(data={"token": token, "user_id": user.id, "username": user.username}, msg="登录成功")


@router.post("/page/register")
async def app_page_register(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    app_id = body.get('app_id', '')
    username = (body.get('username') or '').strip()
    password = body.get('password', '')
    app = require_app(app_id, db)
    if not app:
        return fail(code=401, msg="软件无效或已禁用")
    if not username or not password or len(password) < 6:
        return fail(msg="用户名必填，密码至少6位")
    if get_app_user(db, app_id, username):
        return fail(msg="用户名已存在")
    from app.common.security import hash_password
    user = create_app_user(db, app_id, username, hash_password(password))
    return success(data={"user_id": user.id}, msg="注册成功")


@router.post("/page/recharge/create")
async def app_page_recharge_create(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    app_id = body.get('app_id', '')
    token = body.get('token', '')
    goods_type = int(body.get('goods_type', 0))
    app = require_app(app_id, db)
    if not app:
        return fail(code=401, msg="软件无效或已禁用")
    payload = parse_token(token)
    if not payload or payload.get('app_id') != app_id:
        return fail(code=401, msg="登录已过期")
    amount = _app_price(app, goods_type)
    if amount <= 0:
        return fail(msg="套餐不存在")
    order_sn = 'SA2' + str(int(time.time())) + str(random.randint(1000, 9999))
    create_app_order(db, app_id, order_sn, payload['user_id'], 'wechat', goods_type, amount)
    pay_url = _create_native_pay(order_sn, amount)
    return success(data={"order_sn": order_sn, "amount": amount, "pay_url": pay_url}, msg="下单成功")


# ============ 1. 软件自助注册 ============
def _validate_notify_url(url: str) -> bool:
    """防SSRF：校验 notify_url 不为内网地址"""
    if not url:
        return True
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    host = (parsed.hostname or '').lower()
    if host in ('127.0.0.1', 'localhost', '0.0.0.0', '169.254.169.254', '[::1]'):
        return False
    if host.startswith('10.') or host.startswith('172.') or host.startswith('192.168.'):
        return False
    return True


@router.post("/register")
@limiter.limit("3/minute")
async def app_register(request: Request, data: dict, db: Session = Depends(get_db)):
    app_name = (data.get('app_name') or '').strip()
    notify_url = (data.get('notify_url') or '').strip()
    logo_url = (data.get('logo_url') or '').strip()
    if not app_name or len(app_name) > 100:
        return fail(msg="软件名称必填且不超过100字")
    if not _validate_notify_url(notify_url):
        return fail(msg="notify_url 不合法（禁止内网地址）")
    app_id = 'APP' + str(int(time.time())) + str(random.randint(100, 999))
    app_key = _md5(str(time.time()) + str(random.random()) + app_name)[:32]
    app = create_app(db, app_id, app_key, app_name, logo_url or None, notify_url or None)
    return success(data={"app_id": app.app_id, "app_key": app.app_key},
                   msg="注册成功，请妥善保存 app_key")


# ============ 2. 软件用户注册 ============
@router.post("/user/register")
async def app_user_register(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    app_id = body.get('app_id', '')
    username = (body.get('username') or '').strip()
    password = body.get('password', '')
    sign = body.get('sign', '')
    timestamp = body.get('timestamp', '')
    app = require_app(app_id, db)
    if not app:
        return fail(code=401, msg="软件无效或已禁用")
    if not verify_sign(app.app_key, body, sign, timestamp):
        return fail(code=403, msg="签名无效")
    if not username or not password or len(password) < 6:
        return fail(msg="用户名必填，密码至少6位")
    if get_app_user(db, app_id, username):
        return fail(msg="用户名已存在")
    from app.common.security import hash_password
    user = create_app_user(db, app_id, username, hash_password(password))
    return success(data={"user_id": user.id}, msg="注册成功")


# ============ 3. 软件用户登录 ============
@router.post("/user/login")
async def app_user_login(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    app_id = body.get('app_id', '')
    username = (body.get('username') or '').strip()
    password = body.get('password', '')
    sign = body.get('sign', '')
    timestamp = body.get('timestamp', '')
    app = require_app(app_id, db)
    if not app:
        return fail(code=401, msg="软件无效或已禁用")
    if not verify_sign(app.app_key, body, sign, timestamp):
        return fail(code=403, msg="签名无效")
    user = get_app_user(db, app_id, username)
    if not user:
        return fail(code=401, msg="用户名或密码错误")
    from app.common.security import verify_password
    if not verify_password(password, user.password):
        return fail(code=401, msg="用户名或密码错误")
    if user.status != 1:
        return fail(code=403, msg="账号已封禁")
    user.last_login_time = datetime.now()
    db.commit()
    token = create_token(user_id=user.id, username=user.username, app_id=app_id)
    return success(data={
        "token": token,
        "user_id": user.id,
        "username": user.username,
        "vip_type": user.vip_type,
        "vip_expire_time": user.vip_expire_time.strftime("%Y-%m-%d %H:%M:%S") if user.vip_expire_time else None
    }, msg="登录成功")


# ============ 4. 鉴权（客户端启动校验）============
@router.get("/user/auth")
async def app_user_auth(app_id: str, token: str, db: Session = Depends(get_db)):
    payload = parse_token(token)
    if not payload or payload.get('app_id') != app_id:
        return fail(code=401, msg="登录已过期")
    user = get_app_user_by_id(db, app_id, payload['user_id'])
    if not user or user.status != 1:
        return fail(code=401, msg="账号异常")
    now = datetime.now()
    if user.vip_expire_time and user.vip_expire_time < now:
        user.vip_type = 0
        db.commit()
        return fail(code=403, msg="权限已过期")
    return success(data={
        "user_id": user.id,
        "username": user.username,
        "vip_type": user.vip_type,
        "vip_expire_time": user.vip_expire_time.strftime("%Y-%m-%d %H:%M:%S") if user.vip_expire_time else None
    }, msg="权限正常")


# ============ 5. 充值下单 ============
@router.post("/recharge/create")
async def app_recharge_create(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    app_id = body.get('app_id', '')
    token = body.get('token', '')
    goods_type = int(body.get('goods_type', 0))
    sign = body.get('sign', '')
    timestamp = body.get('timestamp', '')
    app = require_app(app_id, db)
    if not app:
        return fail(code=401, msg="软件无效或已禁用")
    if not verify_sign(app.app_key, body, sign, timestamp):
        return fail(code=403, msg="签名无效")
    payload = parse_token(token)
    if not payload or payload.get('app_id') != app_id:
        return fail(code=401, msg="登录已过期")
    amount = _app_price(app, goods_type)
    if amount <= 0:
        return fail(msg="套餐不存在")
    order_sn = 'SA2' + str(int(time.time())) + str(random.randint(1000, 9999))
    create_app_order(db, app_id, order_sn, payload['user_id'], 'wechat', goods_type, amount)
    pay_url = _create_native_pay(order_sn, amount)
    return success(data={
        "order_sn": order_sn,
        "amount": amount,
        "pay_url": pay_url
    }, msg="下单成功")


# ============ 6. 订单查询 ============
@router.get("/recharge/query")
async def app_recharge_query(app_id: str, token: str, order_sn: str, db: Session = Depends(get_db)):
    payload = parse_token(token)
    if not payload or payload.get('app_id') != app_id:
        return fail(code=401, msg="登录已过期")
    order = get_app_order_by_sn(db, order_sn)
    if not order or order.app_id != app_id or order.user_id != payload['user_id']:
        return fail(msg="订单不存在")
    return success(data={
        "order_sn": order.order_sn,
        "amount": float(order.amount),
        "goods_type": order.goods_type,
        "status": order.status,
        "pay_time": order.pay_time.strftime("%Y-%m-%d %H:%M:%S") if order.pay_time else None
    }, msg="ok")


# ============ 7. 订单列表 ============
@router.get("/recharge/list")
async def app_recharge_list(app_id: str, token: str, db: Session = Depends(get_db)):
    payload = parse_token(token)
    if not payload or payload.get('app_id') != app_id:
        return fail(code=401, msg="登录已过期")
    orders = list_app_orders(db, app_id, payload['user_id'])
    return success(data=[{
        "order_sn": o.order_sn,
        "amount": float(o.amount),
        "goods_type": o.goods_type,
        "status": o.status,
        "create_time": o.create_time.strftime("%Y-%m-%d %H:%M:%S") if o.create_time else None
    } for o in orders], msg="ok")


# ============ 8. 支付成功回调（网关→softapi→转发软件notify_url）============
@router.post("/recharge/callback")
async def app_recharge_callback(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("X-Pay-Token", "")
    if token != os.environ.get("PAY_GATEWAY_TOKEN", ""):
        return fail(msg="签名无效")
    body = await request.json()
    order_sn = body.get("order_no", "")
    status = body.get("status", 0)
    if status != 1 or not order_sn:
        return fail(msg="无效回调")
    order = get_app_order_by_sn(db, order_sn)
    if not order:
        return fail(msg="订单不存在")
    if order.status == 0:
        update_app_order_paid(db, order_sn, order_sn)
        user = get_app_user_by_id(db, order.app_id, order.user_id)
        if user:
            now = datetime.now()
            base = user.vip_expire_time if (user.vip_expire_time and user.vip_expire_time > now) else now
            days = GOODS_DAYS.get(order.goods_type)
            new_exp = None if days is None else base + timedelta(days=days)
            old_exp = user.vip_expire_time
            old_vip = user.vip_type
            update_app_user_vip(db, user.id, order.goods_type, new_exp)
            # 记录开通日志
            from app.models.app_vip_log import AppVipLog
            log = AppVipLog(app_id=order.app_id, user_id=user.id, username=user.username,
                            order_sn=order_sn, old_vip_type=old_vip, new_vip_type=order.goods_type,
                            old_expire_time=old_exp, new_expire_time=new_exp,
                            operate_type="微信充值", operator="system")
            db.add(log)
            db.commit()
            logger.info(f"[{order.app_id}]用户{user.username}充值成功, VIP{order.goods_type}, 过期:{new_exp}")
    # 转发到软件 notify_url
    app = get_app_by_id(db, order.app_id)
    if app and app.notify_url and order.notify_status == 0:
        try:
            _notify_software(app, order)
            mark_app_order_notified(db, order_sn)
        except Exception as e:
            logger.error(f"转发软件回调失败 {app.notify_url}: {e}")
    return success(msg="权限开通成功")


def _notify_software(app, order):
    """POST 到软件 notify_url（带签名）"""
    import urllib.request
    ts = str(int(time.time()))
    payload = {
        "app_id": app.app_id,
        "order_sn": order.order_sn,
        "amount": float(order.amount),
        "goods_type": order.goods_type,
        "user_id": order.user_id,
        "status": 1,
        "timestamp": ts,
    }
    sign = _md5(app.app_id + f"amount{payload['amount']}" + f"goods_type{order.goods_type}"
                + f"order_sn{order.order_sn}" + f"status1" + f"timestamp{ts}"
                + f"user_id{order.user_id}" + app.app_key + ts)
    payload["sign"] = sign
    req = urllib.request.Request(
        app.notify_url,
        data=_json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    return resp.status
