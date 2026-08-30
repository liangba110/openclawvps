from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random, time
from app.crud.order_crud import create_order, get_order_by_sn, update_order_paid
from app.crud.user_crud import get_user_by_id, update_user_vip
from app.crud.vip_log_crud import create_vip_log
from app.config.logger import logger

GOODS_PRICE = {
    1: 9.9,
    2: 29.9,
    3: 199.9,
    4: 520.0,
    5: 1.0
}

def gen_order_sn() -> str:
    # SA前缀 = 统一支付网关回调路由标识（SA→softapi.openai2000.cn）
    # 时间戳+4位随机+4位随机（更难预测）
    import secrets
    return 'SA' + str(int(time.time())) + secrets.token_hex(4)

def create_recharge_order(db: Session, user_id: int, goods_type: int, pay_type: str):
    order_sn = gen_order_sn()
    amount = GOODS_PRICE.get(goods_type, 0)
    if amount <= 0:
        return False, "套餐不存在"
    order = create_order(db, order_sn, user_id, pay_type, goods_type, amount)
    # 调用统一支付网关 Native 扫码（商户1114539763，pay.openai2000.cn）
    pay_url = _create_native_pay(order_sn, amount)
    return True, {
        "order_sn": order_sn,
        "amount": float(amount),
        "pay_type": pay_type,
        "pay_url": pay_url
    }

def _create_native_pay(order_sn: str, amount: float) -> str:
    """调统一支付网关 /api/v1/wxpay/native 获取微信扫码链接"""
    import urllib.request, json as _json
    payload = _json.dumps({
        "out_trade_no": order_sn,
        "amount": amount,
        "subject": "广告信息展示服务"
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:5005/api/v1/wxpay/native",
        data=payload,
        headers={"Content-Type": "application/json"})
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

def get_new_expire_time(old_expire, goods_type: int):
    now = datetime.now()
    base_time = old_expire if (old_expire and old_expire > now) else now
    if goods_type == 1 or goods_type == 5:
        return base_time + timedelta(days=1)
    elif goods_type == 2:
        return base_time + timedelta(days=30)
    elif goods_type == 3:
        return base_time + timedelta(days=365)
    else:
        return None

def recharge_callback_handle(db: Session, order_sn: str, transaction_id: str):
    order = get_order_by_sn(db, order_sn)
    if not order or order.status != 0:
        return False, "订单无效或已支付"

    user = get_user_by_id(db, order.user_id)
    if not user:
        return False, "用户不存在"

    old_vip = user.vip_type
    old_exp = user.vip_expire_time

    new_exp = get_new_expire_time(old_exp, order.goods_type)
    new_vip = order.goods_type

    update_user_vip(db, user.id, new_vip, new_exp)
    update_order_paid(db, order_sn, transaction_id)
    create_vip_log(
        db=db,
        user_id=user.id,
        order_sn=order_sn,
        old_vip_type=old_vip,
        new_vip_type=new_vip,
        old_expire=old_exp,
        new_expire=new_exp,
        operate_type="充值续费"
    )
    logger.info(f"用户{user.username}充值成功，自动开通VIP{new_vip}，过期时间：{new_exp}")
    return True, "权限开通成功"
