from sqlalchemy import Column, Integer, String, DateTime, SmallInteger
from app.db.base import Base
from datetime import datetime

class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    status = Column(SmallInteger, default=1, comment="1正常 0封禁")
    vip_type = Column(SmallInteger, default=0, comment="0普通 1日卡 2月卡 3年卡 4永久")
    vip_expire_time = Column(DateTime, nullable=True)
    last_login_time = Column(DateTime, nullable=True)
    create_time = Column(DateTime, default=datetime.now)
