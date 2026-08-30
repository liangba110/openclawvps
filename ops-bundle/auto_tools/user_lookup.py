#!/usr/bin/env python3
"""
用户详情查询 — 自动生成于2026-08-29 02:43
一条命令查用户完整信息（基本信息+订单+余额+搭子）
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

def cmd_user_detail(args):
    """用户完整画像"""
    if not args:
        return fail('用法: opsctl user <关键词>')
    kw = args[0]
    MYSQL = "mysql -uroot -p'huizhiyun2026' -N huizhiyun"

    # 基本信息
    out, _ = run(f"{MYSQL} -e \"SELECT id, nickname, phone, balance, created_at FROM user WHERE nickname LIKE '%{kw}%' OR phone LIKE '%{kw}%' LIMIT 5;\"")

    # 该用户的订单
    out2, _ = run(f"{MYSQL} -e \"SELECT o.id, o.amount, o.status, o.created_at FROM orders o JOIN user u ON u.id=o.user_id WHERE u.nickname LIKE '%{kw}%' ORDER BY o.id DESC LIMIT 10;\"")

    # 该用户的搭子
    out3, _ = run(f"{MYSQL} -e \"SELECT c.id, c.is_online, c.expires_at FROM companion c JOIN user u ON u.id=c.user_id WHERE u.nickname LIKE '%{kw}%';\"")

    return {'status': 'ok', 'user': out, 'orders': out2, 'companions': out3}


# ── CLI入口 ──
if __name__ == '__main__':
    args = sys.argv[1:]
    # 查找cmd_开头的函数
    func_name = 'cmd_user_lookup'
    # 动态调用
    for name, obj in list(globals().items()):
        if name.startswith('cmd_') and callable(obj):
            result = obj(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            break
