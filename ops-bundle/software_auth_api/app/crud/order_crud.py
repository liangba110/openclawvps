from sqlalchemy.orm import Session
from app.models.order import RechargeOrder
from datetime import datetime

def create_order(db: Session, order_sn: str, user_id: int, pay_type: str, goods_type: int, amount: float):
    order = RechargeOrder(
        order_sn=order_sn,
        user_id=user_id,
        pay_type=pay_type,
        goods_type=goods_type,
        amount=amount
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order

def get_order_by_sn(db: Session, order_sn: str):
    return db.query(RechargeOrder).filter(RechargeOrder.order_sn == order_sn).first()

def update_order_paid(db: Session, order_sn: str, transaction_id: str):
    order = get_order_by_sn(db, order_sn)
    if order and order.status == 0:
        order.status = 1
        order.pay_time = datetime.now()
        order.transaction_id = transaction_id
        db.commit()
        return True
    return False

def get_user_order_list(db: Session, user_id: int):
    return db.query(RechargeOrder).filter(RechargeOrder.user_id == user_id).order_by(RechargeOrder.create_time.desc()).all()
