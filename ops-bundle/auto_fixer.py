#!/usr/bin/env python3
"""
auto_fixer.py — 智能修复引擎（集成事件总线+学习闭环）
"""
import os
import sys
import json
import subprocess
import re
import time
from datetime import datetime
from pathlib import Path

from event_bus import bus
from self_learning import learner

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except:
        return '', -1

# ═══════════════════════════════════════════
# 修复记录（带学习反馈）
# ═══════════════════════════════════════════

def fix_with_learning(issue):
    """执行修复并记录到学习库"""
    if not issue.get('auto_fix'):
        return {'status': 'skip', 'reason': '不可自动修复'}

    cmd = issue.get('fix_cmd', '')
    if not cmd:
        return {'status': 'skip', 'reason': '无修复命令'}

    start = time.time()
    out, code = run(cmd, timeout=60)
    duration = int((time.time() - start) * 1000)
    success = code == 0

    # 记录到学习库
    learner.record_fix(
        symptom=issue.get('title', issue.get('id', 'unknown')),
        cause=issue.get('error', ''),
        action=cmd,
        success=success,
        service=issue.get('id', '').split('_')[0],
        duration_ms=duration
    )

    # 发事件
    bus.emit('fix_executed', {
        'issue_id': issue.get('id'),
        'command': cmd,
        'success': success,
        'duration_ms': duration,
    }, source='auto_fixer')

    return {
        'status': 'fixed' if success else 'failed',
        'command': cmd,
        'output': out[:200],
        'exit_code': code,
        'duration_ms': duration,
    }

# ═══════════════════════════════════════════
# 检测器
# ═══════════════════════════════════════════

def check_nginx_config():
    out, code = run("sudo nginx -t 2>&1")
    if code != 0:
        return {
            'id': 'nginx_config', 'title': 'Nginx配置语法错误',
            'severity': 'critical', 'auto_fix': True,
            'fix_cmd': 'sudo nginx -t && sudo systemctl reload nginx',
            'error': out[:200]
        }
    return None

def check_service_stuck():
    out, _ = run("ps aux --sort=-%cpu | head -5 | tail -4")
    issues = []
    for line in out.split('\n'):
        parts = line.split()
        if len(parts) >= 11:
            try:
                cpu = float(parts[2])
                if cpu > 95:
                    pid = parts[1]
                    cmd = ' '.join(parts[10:])[:80]
                    issues.append({
                        'id': f'stuck_{pid}', 'title': f'进程卡死: CPU {cpu}% (PID {pid})',
                        'severity': 'critical', 'auto_fix': True,
                        'fix_cmd': f'kill -9 {pid}', 'error': cmd
                    })
            except:
                pass
    return issues if issues else None

def check_zombie_processes():
    out, _ = run("ps aux | awk '$8 ~ /Z/ {print $2, $11}'")
    if out.strip():
        issues = []
        for line in out.strip().split('\n'):
            parts = line.split(maxsplit=1)
            if parts:
                issues.append({
                    'id': f'zombie_{parts[0]}', 'title': f'僵尸进程: PID {parts[0]}',
                    'severity': 'warn', 'auto_fix': True,
                    'fix_cmd': f'kill -9 {parts[0]}',
                    'error': parts[1] if len(parts) > 1 else 'unknown'
                })
        return issues
    return None

def check_disk_inodes():
    out, _ = run("df -i / | tail -1 | awk '{print $5}' | tr -d '%'")
    try:
        pct = int(out)
        if pct >= 80:
            return {
                'id': 'inode_full', 'title': f'Inode使用率{pct}%',
                'severity': 'warn', 'auto_fix': True,
                'fix_cmd': 'find /tmp -type f -mtime +7 -delete',
                'error': f'inode使用{pct}%'
            }
    except:
        pass
    return None

# ═══════════════════════════════════════════
# 扫描+修复（带学习）
# ═══════════════════════════════════════════

def scan_all():
    detectors = [check_nginx_config, check_service_stuck, check_zombie_processes, check_disk_inodes]
    all_issues = []
    for detector in detectors:
        try:
            result = detector()
            if result:
                if isinstance(result, list):
                    all_issues.extend(result)
                else:
                    all_issues.append(result)
        except:
            pass
    return {
        'timestamp': datetime.now().isoformat(),
        'total_issues': len(all_issues),
        'auto_fixable': len([i for i in all_issues if i.get('auto_fix')]),
        'issues': all_issues
    }

def fix_all():
    scan = scan_all()
    results = []
    for issue in scan['issues']:
        if issue.get('auto_fix'):
            result = fix_with_learning(issue)
            results.append({'id': issue['id'], 'title': issue['title'], **result})
    return {
        'timestamp': datetime.now().isoformat(),
        'scanned': scan['total_issues'],
        'fixed': len([r for r in results if r['status'] == 'fixed']),
        'failed': len([r for r in results if r['status'] == 'failed']),
        'results': results
    }

# CLI
if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    if cmd == 'scan':
        print(json.dumps(scan_all(), ensure_ascii=False, indent=2))
    elif cmd == 'fix' and len(sys.argv) > 2:
        scan = scan_all()
        for issue in scan['issues']:
            if issue['id'] == sys.argv[2]:
                print(json.dumps({'issue': issue['title'], **fix_with_learning(issue)}, ensure_ascii=False, indent=2))
                break
    elif cmd == 'fix-all':
        print(json.dumps(fix_all(), ensure_ascii=False, indent=2))
    else:
        print('用法: scan | fix <id> | fix-all')
