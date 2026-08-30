#!/usr/bin/env python3
"""每日健康报告 — 生成系统+业务综合日报"""
import os, sys, json, subprocess
from datetime import datetime
sys.path.insert(0, os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))

def run(cmd):
    try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15).stdout.strip()
    except: return ''

def main():
    lines = [f"📊 每日健康报告 | {datetime.now().strftime('%Y-%m-%d %H:%M')}", "═" * 35]
    
    # 服务状态
    services = {'ttdazi': '5002', 'ttdazi-pay': '5005', 'aiweb': '5003'}
    for name, port in services.items():
        code = run(f"curl -sk -o /dev/null -w '%{{http_code}}' --max-time 3 http://127.0.0.1:{port}/api/health 2>/dev/null")
        icon = '✅' if code == '200' else '❌'
        lines.append(f"  {icon} {name}: HTTP {code}")
    
    for svc in ['mysql', 'caddy', 'ops-engine']:
        active = run(f"systemctl is-active {svc}")
        icon = '✅' if active == 'active' else '❌'
        lines.append(f"  {icon} {svc}: {active}")
    
    # 资源
    cpu = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
    mem = run("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
    disk = run("df / | tail -1 | awk '{print $5}' | tr -d '%'")
    disk_data = run("df /data/disk 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%'")
    lines.append(f"\n💻 资源: CPU={cpu}% 内存={mem}% 系统盘={disk}% 数据盘={disk_data}%")
    
    # SSL
    for host in ['www.ttdazi.xyz', 'aiweb.openai2000.cn', 'pay.openai2000.cn', 'www.openai2000.cn']:
        out = run(f"echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2")
        if out:
            try:
                from email.utils import parsedate_to_datetime
                days = (parsedate_to_datetime(out) - datetime.now(parsedate_to_datetime(out).tzinfo)).days
                icon = '✅' if days > 30 else ('⚠️' if days > 14 else '❌')
                lines.append(f"  {icon} SSL {host}: {days}天")
            except: pass
    
    # 备份
    backups = run("ls -d /data/disk/daily_* 2>/dev/null | wc -l")
    lines.append(f"\n💾 备份: {backups}个 (保留15天)")
    
    # 引擎状态
    try:
        from engine import load_state
        escalation = load_state('escalation')
        pending = len(escalation.get('pending', []))
        lines.append(f"🛡️ 引擎: 待处理告警 {pending}条")
    except: pass
    
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
