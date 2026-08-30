from sqlalchemy.orm import Session
from datetime import datetime
from app.crud.user_crud import get_user_by_username, create_user, update_user_login_time, get_user_by_id
from app.common.security import hash_password, verify_password, create_token
from app.config.settings import settings
from app.config.logger import logger
import redis

r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_DB, decode_responses=True)

def user_register(db: Session, username: str, password: str):
    if get_user_by_username(db, username):
        return False, "账号已存在"
    pwd_hash = hash_password(password)
    create_user(db, username, pwd_hash)
    logger.info(f"新用户注册成功：{username}")
    return True, "注册成功"

def user_login(db: Session, username: str, password: str):
    lock_key = f"lock:{username}"
    if r.exists(lock_key):
        return False, f"账号已锁定，请{r.ttl(lock_key)}秒后重试"

    user = get_user_by_username(db, username)
    if not user:
        return False, "账号或密码错误"

    if user.status != 1:
        return False, "账号已被封禁"

    if not verify_password(password, user.password):
        err_key = f"err:{username}"
        count = r.incr(err_key)
        r.expire(err_key, settings.LOCK_SECOND)
        if count >= settings.ERROR_MAX_COUNT:
            r.setex(lock_key, settings.LOCK_SECOND, "1")
            logger.warning(f"账号{username}密码错误过多，已锁定")
            return False, "密码错误次数过多，账号已临时锁定"
        return False, "账号或密码错误"

    r.delete(f"err:{username}")
    update_user_login_time(db, user.id)
    token = create_token(user.id, user.username)

    now = datetime.now()
    vip_valid = True
    if user.vip_type != 4 and user.vip_expire_time and user.vip_expire_time < now:
        vip_valid = False

    data = {
        "token": token,
        "user_id": user.id,
        "username": user.username,
        "vip_type": user.vip_type,
        "vip_expire_time": user.vip_expire_time.strftime("%Y-%m-%d %H:%M:%S") if user.vip_expire_time else None,
        "vip_valid": vip_valid
    }
    logger.info(f"用户登录成功：{username}")
    return True, data

def check_user_auth(db: Session, user_id: int):
    user = get_user_by_id(db, user_id)
    if not user or user.status != 1:
        return False, "用户不存在或账号异常"
    now = datetime.now()
    if user.vip_type != 4 and user.vip_expire_time and user.vip_expire_time < now:
        return False, "会员权限已过期"
    return True, "校验通过"
