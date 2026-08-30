from sqlalchemy.orm import Session
from app.models.vip_log import VipLog

def create_vip_log(
    db: Session,
    user_id: int,
    order_sn: str,
    old_vip_type: int,
    new_vip_type: int,
    old_expire,
    new_expire,
    operate_type: str
):
    log = VipLog(
        user_id=user_id,
        order_sn=order_sn,
        old_vip_type=old_vip_type,
        new_vip_type=new_vip_type,
        old_expire_time=old_expire,
        new_expire_time=new_expire,
        operate_type=operate_type
    )
    db.add(log)
    db.commit()
