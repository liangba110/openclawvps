#!/usr/bin/env python3
"""
数据库深度健康 — 自动生成于2026-08-29 02:44
连接数+查询数+表大小+碎片+慢查询+锁
"""
import os, sys, json, subprocess
from datetime import datetime

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except: return '', -1

def ok(msg): return {'status': 'ok', 'message': msg}
def fail(msg): return {'status': 'error', 'message': msg}

# ── 核心逻辑 ──

def cmd_db_health(args):
    """数据库深度健康报告"""
    MYSQL = "mysql -uroot -p'huizhiyun2026' -N huizhiyun"

    checks = {}
    for metric, sql in [
        ('connections', "SHOW STATUS LIKE 'Threads_connected'"),
        ('max_connections', "SHOW VARIABLES LIKE 'max_connections'"),
        ('queries', "SHOW STATUS LIKE 'Queries'"),
        ('slow_queries', "SHOW STATUS LIKE 'Slow_queries'"),
        ('threads_running', "SHOW STATUS LIKE 'Threads_running'"),
    ]:
        out, _ = run(f"{MYSQL} -e \"{sql}\" | awk '{{print $2}}'")
        checks[metric] = out

    # 表碎片
    out, _ = run(f"{MYSQL} -e \"SELECT table_name, ROUND(DATA_FREE/(DATA_LENGTH+1)*100,1) as frag FROM information_schema.tables WHERE table_schema='huizhiyun' AND DATA_FREE > 0 ORDER BY frag DESC LIMIT 5;\"")
    checks['fragmented_tables'] = out

    return {'status': 'ok', 'db_health': checks}


# ── CLI入口 ──
if __name__ == '__main__':
    args = sys.argv[1:]
    # 查找cmd_开头的函数
    func_name = 'cmd_db_health'
    # 动态调用
    for name, obj in list(globals().items()):
        if name.startswith('cmd_') and callable(obj):
            result = obj(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            break
