#!/usr/bin/env python3
from event_bus import bus
"""
alerts — 实时告警推送模块
支持: 文件记录 + QQ推送(通过Hermes) + 微信推送 + 控制台

用法:
  python3 /opt/ttdazi/ops/alerts.py send "⚠️ 磁盘80%" --level warn --channel all
  python3 /opt/ttdazi/ops/alerts.py history          # 查看告警历史
  python3 /opt/ttdazi/ops/alerts.py stats             # 告警统计
  python3 /opt/ttdazi/ops/alerts.py test              # 测试推送

告警级别: info / warn / critical / emergency
推送渠道: file / console / qq / wechat / all
"""
import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
ALERTS_DIR = BASE_DIR / 'data' / 'alerts'
ALERTS_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = ALERTS_DIR / 'history.jsonl'
SUPPRESS_FILE = ALERTS_DIR / 'suppress.json'  # 静默规则

# ═══════════════════════════════════════════
# 告警发送
# ═══════════════════════════════════════════


def _alert_on_event(data):
    """事件触发时自动告警"""
    try:
        severity = data.get('severity', 'info')
        if severity in ('critical', 'emergency'):
            send_alert(data.get('message', str(data)), level=severity, source='event_bus')
    except Exception:
        pass

bus.on('rule_error', _alert_on_event)
bus.on('escalation', _alert_on_event)

def send_alert(message, level='warn', source='ops', channel='all', suppress_key=None):
    """
    发送告警
    
    Args:
        message: 告警内容
        level: info/warn/critical/emergency
        source: 来源(engine/opsctl/manual)
        channel: file/console/qq/wechat/all
        suppress_key: 静默key（同一key在冷却期内不重复发送）
    """
    # 检查静默
    if suppress_key and is_suppressed(suppress_key):
        return {'status': 'suppressed', 'message': f'静默中: {suppress_key}'}

    alert = {
        'timestamp': datetime.now().isoformat(),
        'level': level,
        'source': source,
        'message': message,
        'hostname': os.uname().nodename,
    }

    results = {}

    # 1. 文件记录（始终执行）
    results['file'] = save_to_file(alert)

    # 2. 控制台输出
    if channel in ('console', 'all'):
        results['console'] = print_to_console(alert)

    # 3. QQ推送（通过Hermes cron的escalation机制）
    if channel in ('qq', 'all'):
        results['qq'] = push_to_qq(alert)

    # 4. 微信推送（通过公众号模板消息）
    if channel in ('wechat', 'all'):
        results['wechat'] = push_to_wechat(alert)

    # 设置静默冷却
    if suppress_key:
        set_suppress(suppress_key, cooldown_minutes=get_cooldown(level))

    return {'status': 'sent', 'alert': alert, 'results': results}

# ═══════════════════════════════════════════
# 推送渠道
# ═══════════════════════════════════════════

def save_to_file(alert):
    """保存到历史文件"""
    try:
        with open(HISTORY_FILE, 'a') as f:
            f.write(json.dumps(alert, ensure_ascii=False) + '\n')

        # 清理30天前的记录
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        lines = []
        if HISTORY_FILE.exists():
            for line in HISTORY_FILE.read_text().strip().split('\n'):
                if line:
                    try:
                        entry = json.loads(line)
                        if entry.get('timestamp', '') > cutoff:
                            lines.append(line)
                    except:
                        pass
        HISTORY_FILE.write_text('\n'.join(lines) + '\n' if lines else '')
        return True
    except Exception:
        return False

def print_to_console(alert):
    """控制台输出"""
    icons = {'info': 'ℹ️', 'warn': '⚠️', 'critical': '🚨', 'emergency': '🔥'}
    icon = icons.get(alert['level'], '❓')
    ts = alert['timestamp'][:19]
    print(f"[{ts}] {icon} [{alert['level'].upper()}] {alert['message']}")
    return True

def push_to_qq(alert):
    """
    推送到QQ — 通过写入escalation文件，Hermes下次轮询时读取并发送
    优先级: emergency/critical立即推送，warn/info积累后批量推送
    """
    escalation_file = BASE_DIR / 'state' / 'escalation.json'
    try:
        data = {'pending': []}
        if escalation_file.exists():
            data = json.loads(escalation_file.read_text())

        if 'pending' not in data:
            data['pending'] = []

        data['pending'].append({
            'timestamp': alert['timestamp'],
            'severity': alert['level'],
            'message': alert['message'],
            'source': alert.get('source', 'ops'),
            'delivered': False
        })

        # 只保留最近50条
        data['pending'] = data['pending'][-50:]
        escalation_file.write_text(json.dumps(data, ensure_ascii=False, indent=1))

        # emergency/critical立即触发Hermes
        if alert['level'] in ('emergency', 'critical'):
            trigger_hermes_delivery(alert)

        return True
    except Exception:
        return False

def push_to_wechat(alert):
    """
    推送到微信 — 通过公众号客服消息
    需要已配置公众号（wxd274e174ddadd4cb）
    """
    # 写入待发送队列，由定时任务批量发送
    queue_file = ALERTS_DIR / 'wechat_queue.jsonl'
    try:
        with open(queue_file, 'a') as f:
            f.write(json.dumps(alert, ensure_ascii=False) + '\n')
        return True
    except Exception:
        return False

def trigger_hermes_delivery(alert):
    """触发Hermes立即推送（通过写入特定文件）"""
    trigger_file = ALERTS_DIR / 'urgent_alert.json'
    try:
        trigger_file.write_text(json.dumps({
            'timestamp': alert['timestamp'],
            'level': alert['level'],
            'message': alert['message'],
            'hostname': alert.get('hostname', ''),
        }, ensure_ascii=False))
    except Exception:
        pass

# ═══════════════════════════════════════════
# 静默管理（防止重复告警）
# ═══════════════════════════════════════════

def is_suppressed(key):
    """检查是否在静默期"""
    if not SUPPRESS_FILE.exists():
        return False
    try:
        data = json.loads(SUPPRESS_FILE.read_text())
        if key in data:
            until = datetime.fromisoformat(data[key])
            return datetime.now() < until
    except:
        pass
    return False

def set_suppress(key, cooldown_minutes=30):
    """设置静默"""
    data = {}
    if SUPPRESS_FILE.exists():
        try:
            data = json.loads(SUPPRESS_FILE.read_text())
        except:
            pass
    until = (datetime.now() + timedelta(minutes=cooldown_minutes)).isoformat()
    data[key] = until
    SUPPRESS_FILE.write_text(json.dumps(data, indent=1))

def get_cooldown(level):
    """根据级别设置冷却时间（分钟）"""
    return {'info': 60, 'warn': 30, 'critical': 10, 'emergency': 5}.get(level, 30)

# ═══════════════════════════════════════════
# 告警历史查询
# ═══════════════════════════════════════════

def get_history(hours=24, level=None):
    """获取告警历史"""
    if not HISTORY_FILE.exists():
        return []

    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    alerts = []
    for line in HISTORY_FILE.read_text().strip().split('\n'):
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get('timestamp', '') > cutoff:
                if level is None or entry.get('level') == level:
                    alerts.append(entry)
        except:
            pass
    return alerts

def get_stats(hours=24):
    """告警统计"""
    alerts = get_history(hours)
    stats = {'total': len(alerts), 'by_level': {}, 'by_source': {}, 'by_hour': {}}
    for a in alerts:
        level = a.get('level', 'unknown')
        source = a.get('source', 'unknown')
        hour = a.get('timestamp', '')[:13]  # YYYY-MM-DDTHH

        stats['by_level'][level] = stats['by_level'].get(level, 0) + 1
        stats['by_source'][source] = stats['by_source'].get(source, 0) + 1
        stats['by_hour'][hour] = stats['by_hour'].get(hour, 0) + 1

    return stats

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == 'send' and len(sys.argv) > 2:
        message = sys.argv[2]
        level = 'warn'
        channel = 'all'
        for i, arg in enumerate(sys.argv[3:], 3):
            if arg == '--level' and i + 1 < len(sys.argv):
                level = sys.argv[i + 1]
            elif arg == '--channel' and i + 1 < len(sys.argv):
                channel = sys.argv[i + 1]
        result = send_alert(message, level=level, channel=channel)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == 'history':
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        alerts = get_history(hours)
        print(json.dumps(alerts, ensure_ascii=False, indent=2))

    elif cmd == 'stats':
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        stats = get_stats(hours)
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif cmd == 'test':
        result = send_alert('🧪 告警测试 — 系统正常', level='info', channel='all')
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(f'未知命令: {cmd}')
