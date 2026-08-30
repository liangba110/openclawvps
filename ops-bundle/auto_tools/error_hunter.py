#!/usr/bin/env python3
"""
错误猎手 — 自动生成于2026-08-29 02:44
扫描所有日志找最近错误，按严重度排序
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

def cmd_error_hunt(args):
    """扫描所有日志找错误"""
    log_files = {
        'ttdazi': '/opt/ttdazi/backend/app/ttdazi.log',
        'pay': '/var/log/ttdazi_pay.log',
        'aiweb': '/var/log/aiweb.log',
        'auth': '/var/log/auth.log',
    }
    errors = []
    for name, path in log_files.items():
        if not os.path.exists(path):
            continue
        out, _ = run(f"grep -iE 'ERROR|Exception|Traceback|FATAL|critical' {path} | tail -5")
        for line in out.split('\n'):
            if line.strip():
                errors.append({'source': name, 'error': line.strip()[:200]})

    errors.sort(key=lambda x: x['source'])
    return {'status': 'ok', 'error_count': len(errors), 'errors': errors[:20]}


# ── CLI入口 ──
if __name__ == '__main__':
    args = sys.argv[1:]
    # 查找cmd_开头的函数
    func_name = 'cmd_error_hunter'
    # 动态调用
    for name, obj in list(globals().items()):
        if name.startswith('cmd_') and callable(obj):
            result = obj(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            break
