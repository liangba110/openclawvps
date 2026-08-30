#!/usr/bin/env python3
"""
快速部署（自动判断项目） — 自动生成于2026-08-29 02:44
自动检测改动了哪个项目并部署
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

def cmd_quick_deploy(args):
    """智能部署：自动检测改动"""
    # 检查git状态
    out, _ = run("cd /opt/ttdazi && git status --short 2>/dev/null")
    changed_files = out.strip().split('\n') if out else []

    # 判断项目
    project = 'ttdazi'
    for f in changed_files:
        if 'payment' in f or 'pay' in f:
            project = 'pay'
        elif 'aiweb' in f:
            project = 'aiweb'
        elif 'frontend' in f:
            project = 'ttdazi'

    return cmd_deploy(project)


# ── CLI入口 ──
if __name__ == '__main__':
    args = sys.argv[1:]
    # 查找cmd_开头的函数
    func_name = 'cmd_quick_deploy'
    # 动态调用
    for name, obj in list(globals().items()):
        if name.startswith('cmd_') and callable(obj):
            result = obj(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            break
