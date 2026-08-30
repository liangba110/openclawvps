#!/usr/bin/env python3
"""
qq_push — 读取告警队列，输出格式化消息供Hermes发送
被cron每2分钟调用一次，检查escalation.json中有无未推送的告警
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ESCALATION_FILE = Path('/opt/ttdazi/ops/state/escalation.json')
PUSHED_FILE = Path('/opt/ttdazi/ops/state/pushed_alerts.json')

def load_pushed():
    """已推送的告警ID"""
    if PUSHED_FILE.exists():
        try:
            return set(json.loads(PUSHED_FILE.read_text()))
        except:
            pass
    return set()

def save_pushed(ids):
    """保存已推送ID（只保留最近100个）"""
    ids = list(ids)[-100:]
    PUSHED_FILE.write_text(json.dumps(ids))

def main():
    if not ESCALATION_FILE.exists():
        return

    data = json.loads(ESCALATION_FILE.read_text())
    pending = data.get('pending', [])
    if not pending:
        return

    pushed_ids = load_pushed()

    new_alerts = []
    for alert in pending:
        # 用时间戳+消息作为唯一ID
        alert_id = f"{alert.get('timestamp','')}:{alert.get('message','')[:50]}"
        if alert_id not in pushed_ids:
            new_alerts.append(alert)
            pushed_ids.add(alert_id)

    if not new_alerts:
        return

    # 格式化消息
    icons = {'info': 'ℹ️', 'warn': '⚠️', 'critical': '🚨', 'emergency': '🔥'}
    lines = [f"🛡️ Ops告警 ({len(new_alerts)}条新告警)"]
    lines.append("─" * 30)

    for alert in new_alerts:
        level = alert.get('severity', 'info')
        icon = icons.get(level, '❓')
        ts = alert.get('timestamp', '')[:16].replace('T', ' ')
        msg = alert.get('message', '')
        lines.append(f"{icon} [{ts}] {msg}")

    lines.append("─" * 30)
    lines.append(f"🖥️ 服务器: {Path('/etc/hostname').read_text().strip()}")

    # 输出到stdout（Hermes cron会读取）
    print('\n'.join(lines))

    # 更新已推送记录
    save_pushed(pushed_ids)

    # 清空已推送的pending
    data['pending'] = [a for a in pending if f"{a.get('timestamp','')}:{a.get('message','')[:50]}" not in pushed_ids]
    ESCALATION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
