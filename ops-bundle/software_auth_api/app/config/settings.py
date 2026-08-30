import os


class Settings:
    # 项目
    PROJECT_NAME = "软件登录充值授权API"
    DEBUG = False
    HOST = "0.0.0.0"
    PORT = 8000

    # 数据库
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "software_auth")
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

    # JWT（生产环境必须用随机密钥: python3 -c "import secrets; print(secrets.token_hex(32))"）
    JWT_SECRET = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_HOURS = 24 * 7  # 7天

    # 安全策略
    ERROR_MAX_COUNT = 5       # 密码错误最大次数
    LOCK_SECOND = 600          # 锁定时长(秒) 10分钟

    # 支付回调签名密钥（生产请改为随机强密钥并切换为支付宝RSA2/微信V3官方验签）
    CALLBACK_SIGN_KEY = os.getenv("CALLBACK_SIGN_KEY", "")


settings = Settings()
