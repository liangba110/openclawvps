#!/usr/bin/env python3
"""
log_analyzer — 日志智能分析
不只是grep，而是：模式识别 + 错误分类 + 趋势分析 + 根因推断

用法:
  python3 /opt/ttdazi/ops/log_analyzer.py scan [service]  # 扫描日志
  python3 /opt/ttdazi/ops/log_analyzer.py trend [hours]   # 错误趋势
  python3 /opt/ttdazi/ops/log_analyzer.py pattern         # 识别模式
"""
import os
import sys
import json
import re
import subprocess
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))

LOG_FILES = {
    'auth': '/var/log/auth.log',
    'syslog': '/var/log/syslog',
    'ttdazi': '/opt/ttdazi/backend/app/ttdazi.log',
    'pay': '/var/log/ttdazi_pay.log',
    'aiweb': '/var/log/aiweb.log',
    'nginx-access': '/var/log/nginx/access.log',
    'nginx-error': '/var/log/nginx/error.log',
}

# 错误模式库
ERROR_PATTERNS = {
    'crash': {
        'patterns': [r'Traceback', r'Fatal', r'PANIC', r'Segmentation fault', r'core dumped'],
        'severity': 'critical',
        'category': '崩溃',
        'auto_fix': 'restart_service'
    },
    'memory': {
        'patterns': [r'Out of memory', r'OOM', r'Cannot allocate', r'oom-kill'],
        'severity': 'critical',
        'category': '内存',
        'auto_fix': 'kill_process'
    },
    'disk': {
        'patterns': [r'No space left', r'ENOSPC', r'disk full'],
        'severity': 'critical',
        'category': '磁盘',
        'auto_fix': 'cleanup'
    },
    'network': {
        'patterns': [r'Connection refused', r'ECONNREFUSED', r'ETIMEDOUT', r'Connection reset'],
        'severity': 'warn',
        'category': '网络',
        'auto_fix': None
    },
    'auth': {
        'patterns': [r'Failed password', r'Authentication failure', r'Invalid user'],
        'severity': 'warn',
        'category': '认证',
        'auto_fix': 'block_ip'
    },
    'mysql': {
        'patterns': [r'Too many connections', r'Lock wait timeout', r'Deadlock'],
        'severity': 'warn',
        'category': '数据库',
        'auto_fix': 'optimize_db'
    },
    'nginx': {
        'patterns': [r'upstream timed out', r'upstream prematurely closed', r'502 Bad Gateway'],
        'severity': 'warn',
        'category': 'Web服务',
        'auto_fix': 'restart_service'
    },
    'ssl': {
        'patterns': [r'SSL_CTX', r'certificate verify failed', r'tls alert'],
        'severity': 'warn',
        'category': 'SSL',
        'auto_fix': 'renew_cert'
    },
}

def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ''

def scan_log(log_name, lines=200):
    """扫描单个日志文件"""
    log_path = LOG_FILES.get(log_name, log_name)
    if not os.path.exists(log_path):
        return {'status': 'error', 'message': f'日志不存在: {log_path}'}

    out = run(f"tail -{lines} {log_path}")
    if not out:
        return {'status': 'ok', 'errors': [], 'total_lines': 0}

    errors = []
    for line in out.split('\n'):
        for error_type, config in ERROR_PATTERNS.items():
            for pattern in config['patterns']:
                if re.search(pattern, line, re.IGNORECASE):
                    errors.append({
                        'type': error_type,
                        'category': config['category'],
                        'severity': config['severity'],
                        'message': line.strip()[:200],
                        'auto_fix': config['auto_fix']
                    })
                    break

    # 去重
    seen = set()
    unique_errors = []
    for e in errors:
        key = f"{e['type']}:{e['message'][:80]}"
        if key not in seen:
            seen.add(key)
            unique_errors.append(e)

    return {
        'status': 'ok',
        'log': log_name,
        'path': log_path,
        'total_lines': len(out.split('\n')),
        'errors': unique_errors[:20],
        'error_count': len(unique_errors)
    }

def scan_all():
    """扫描所有日志"""
    results = {}
    for name in LOG_FILES:
        result = scan_log(name)
        if result.get('error_count', 0) > 0:
            results[name] = result

    # 汇总
    total_errors = sum(r.get('error_count', 0) for r in results.values())
    categories = Counter()
    auto_fixable = []
    for r in results.values():
        for e in r.get('errors', []):
            categories[e['category']] += 1
            if e.get('auto_fix'):
                auto_fixable.append(e)

    return {
        'timestamp': datetime.now().isoformat(),
        'logs_scanned': len(LOG_FILES),
        'logs_with_errors': len(results),
        'total_errors': total_errors,
        'by_category': dict(categories.most_common()),
        'auto_fixable': len(auto_fixable),
        'details': results,
        'fix_suggestions': generate_fix_suggestions(results)
    }

def generate_fix_suggestions(results):
    """根据扫描结果生成修复建议"""
    suggestions = []
    for log_name, result in results.items():
        for error in result.get('errors', []):
            fix = error.get('auto_fix')
            if fix and fix not in [s.get('type') for s in suggestions]:
                suggestions.append({
                    'type': fix,
                    'error_type': error['type'],
                    'category': error['category'],
                    'count': 1,
                    'auto_fixable': True
                })
            elif not fix:
                suggestions.append({
                    'type': 'manual',
                    'error_type': error['type'],
                    'category': error['category'],
                    'count': 1,
                    'auto_fixable': False
                })

    # 合并同类
    merged = {}
    for s in suggestions:
        key = s['type']
        if key in merged:
            merged[key]['count'] += s['count']
        else:
            merged[key] = s

    return sorted(merged.values(), key=lambda x: x['count'], reverse=True)[:10]

def error_trend(hours=24):
    """分析错误趋势"""
    log_path = LOG_FILES.get('auth', '/var/log/auth.log')
    if not os.path.exists(log_path):
        return {'status': 'error'}

    # 按小时统计
    hourly = defaultdict(int)
    out = run(f"grep -h 'error\\|Error\\|ERROR' {log_path} 2>/dev/null | tail -500")
    for line in out.split('\n'):
        # 尝试提取时间戳
        match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}|\w+ \d+ \d{2}:\d{2})', line)
        if match:
            ts = match.group(1)
            if ':' in ts and len(ts) >= 13:
                hour = ts[:13]
                hourly[hour] += 1

    return {
        'status': 'ok',
        'period_hours': hours,
        'hourly_errors': dict(sorted(hourly.items())),
        'peak_hour': max(hourly.items(), key=lambda x: x[1])[0] if hourly else None,
        'total': sum(hourly.values())
    }

def detect_patterns():
    """检测日志中的重复模式"""
    patterns = {}
    for name, path in LOG_FILES.items():
        if not os.path.exists(path):
            continue
        out = run(f"tail -500 {path} | grep -i error")
        if not out:
            continue

        # 提取错误签名（去掉时间戳和变量部分）
        signatures = Counter()
        for line in out.split('\n'):
            if not line.strip():
                continue
            # 去掉时间戳
            sig = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', 'TS', line)
            sig = re.sub(r'\d+\.\d+\.\d+\.\d+', 'IP', sig)
            sig = re.sub(r'\b\d{10,}\b', 'ID', sig)
            sig = sig.strip()[:100]
            signatures[sig] += 1

        # 高频签名 = 模式
        for sig, count in signatures.most_common(5):
            if count >= 3:
                if name not in patterns:
                    patterns[name] = []
                patterns[name].append({'pattern': sig, 'count': count})

    return {'status': 'ok', 'patterns': patterns}

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'scan'

    if cmd == 'scan':
        service = sys.argv[2] if len(sys.argv) > 2 else None
        if service:
            result = scan_log(service)
        else:
            result = scan_all()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'trend':
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        result = error_trend(hours)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'pattern':
        result = detect_patterns()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('用法: scan [service] | trend [hours] | pattern')
