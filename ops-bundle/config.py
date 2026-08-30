#!/usr/bin/env python3
"""
config.py — 统一配置加载器
从.env文件读取配置，不再硬编码
"""
import os
from pathlib import Path

# 加载.env
ENV_FILE = Path(__file__).parent / '.env'
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().strip().split('\n'):
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())

# 数据库配置
MYSQL_HOST = os.environ.get('MYSQL_HOST', '127.0.0.1')
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', '3306'))
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
MYSQL_DB = os.environ.get('MYSQL_DB', 'huizhiyun')

# MiMo配置
MIMO_BASE_URL = os.environ.get('MIMO_BASE_URL', 'https://token-plan-cn.xiaomimimo.com/v1')
MIMO_API_KEY = os.environ.get('MIMO_API_KEY', '')
MIMO_MODEL = os.environ.get('MIMO_MODEL', 'mimo-v2.5-pro')

# 路径配置
PROJECT_DIR = Path(os.environ.get('PROJECT_DIR', '/opt/ttdazi'))
OPS_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))

# MySQL命令
import shlex
MYSQL_CMD = f"mysql -h{MYSQL_HOST} -u{MYSQL_USER} -p{shlex.quote(MYSQL_PASSWORD)} -N {MYSQL_DB}"
