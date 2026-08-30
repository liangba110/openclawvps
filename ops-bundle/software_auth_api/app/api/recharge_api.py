from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.schemas.order_schema import CreateOrderSchema
from app.service.recharge_service import create_recharge_order, recharge_callback_handle
from app.common.response import success, fail
from app.common.security import parse_token

router = APIRouter()

@router.post("/create")
async def create_order(token: str, data: CreateOrderSchema, db: Session = Depends(get_db)):
    payload = parse_token(token)
    if not payload:
        return fail(code=401, msg="未登录")
    user_id = payload["user_id"]
    ok, res = create_recharge_order(db, user_id, data.goods_type, data.pay_type)
    if not ok:
        return fail(msg=res)
    return success(data=res)

@router.post("/callback")
async def pay_callback(request: Request, db: Session = Depends(get_db)):
    """统一支付网关回调（JSON: order_no/amount/status/timestamp + X-Pay-Sign）"""
    import hmac, hashlib, time
    from app.config.settings import settings
    
    # 验签：HMAC-SHA256(order_no + amount + status + timestamp, CALLBACK_SIGN_KEY)
    body = await request.json()
    sign = request.headers.get("X-Pay-Sign", "")
    out_trade_no = body.get("order_no", "")
    amount = body.get("amount", 0)
    status = body.get("status", 0)
    timestamp = body.get("timestamp", "")
    
    if not out_trade_no or not sign:
        return fail(msg="缺少签名")
    
    # 构造签名字符串
    sign_str = f"{out_trade_no}{amount}{status}{timestamp}"
    expected = hmac.new(
        settings.CALLBACK_SIGN_KEY.encode(),
        sign_str.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(sign, expected):
        return fail(msg="签名验证失败")
    
    # 检查时间戳（防重放，5分钟内有效）
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:
            return fail(msg="请求过期")
    except:
        return fail(msg="无效时间戳")
    
    if status != 1 or not out_trade_no:
        return fail(msg="无效回调")
    
    ok, msg = recharge_callback_handle(db, out_trade_no, out_trade_no)
    if not ok:
        return fail(msg=msg)
    return success(msg=msg)

@router.get("/list")
async def order_list(token: str, db: Session = Depends(get_db)):
    from app.crud.order_crud import get_user_order_list
    payload = parse_token(token)
    if not payload:
        return fail(code=401, msg="未登录")
    list_data = get_user_order_list(db, payload["user_id"])
    return success(data=list_data)
