from sqlalchemy.orm import Session
from app.models.user import User
from datetime import datetime

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def create_user(db: Session, username: str, password: str):
    db_user = User(username=username, password=password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_login_time(db: Session, user_id: int):
    user = get_user_by_id(db, user_id)
    if user:
        user.last_login_time = datetime.now()
        db.commit()

def update_user_vip(db: Session, user_id: int, vip_type: int, expire_time):
    user = get_user_by_id(db, user_id)
    if user:
        user.vip_type = vip_type
        user.vip_expire_time = expire_time
        db.commit()
        return True
    return False
