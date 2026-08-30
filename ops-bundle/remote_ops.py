#!/usr/bin/env python3
"""
remote_ops — 多服务器管理（SSH远程操作）
A服务器(42.193.113.230) → B服务器(82.157.202.24) 远程运维

用法:
  python3 /opt/ttdazi/ops/remote_ops.py status             # B服务器状态
  python3 /opt/ttdazi/ops/remote_ops.py exec "命令"         # 远程执行
  python3 /opt/ttdazi/ops/remote_ops.py health              # 远程健康检查
  python3 /opt/ttdazi/ops/remote_ops.py deploy <project>    # 远程部署
  python3 /opt/ttdazi/ops/remote_ops.py sync <file>         # 同步文件到B
  python3 /opt/ttdazi/ops/remote_ops.py all-status          # 所有服务器状态
"""
import os
import sys
import json
import subprocess
from datetime import datetime

SERVERS = {
    'A': {'host': '42.193.113.230', 'name': '主服务器', 'user': 'root'},
    'B': {'host': '82.157.202.24', 'name': '反代服务器', 'user': 'ubuntu'},
}

def ssh_exec(host, cmd, user='ubuntu', timeout=30, retries=3):
    """SSH远程执行命令（带超时重连）"""
    for attempt in range(retries):
        import shlex
        ssh_cmd = ["ssh", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=5",
                   "-o", "ServerAliveCountMax=3", "-o", "BatchMode=yes",
                   f"{user}@{host}", cmd]
        try:
            r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 or attempt == retries - 1:
                return r.stdout.strip(), r.returncode
        except subprocess.TimeoutExpired:
            if attempt == retries - 1:
                return 'TIMEOUT', -1
        except Exception as e:
            if attempt == retries - 1:
                return str(e), -1
        import time as _time
        _time.sleep(2 ** attempt)  # 指数退避
    return 'MAX_RETRIES', -1

def scp_to(local_path, remote_path, host, user='ubuntu'):
    """SCP传文件到远程"""
    cmd = f"scp -o ConnectTimeout=10 {local_path} {user}@{host}:{remote_path}"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except:
        return False

def cmd_status(server='B'):
    """远程服务器状态"""
    info = SERVERS.get(server, SERVERS['B'])
    host, user = info['host'], info['user']

    result = {'server': server, 'host': host, 'name': info['name']}

    # 基础信息
    out, code = ssh_exec(host, "hostname && uptime && cat /etc/os-release | head -1", user)
    if code == 0:
        lines = out.split('\n')
        result['hostname'] = lines[0] if lines else ''
        result['uptime'] = lines[1] if len(lines) > 1 else ''
        result['os'] = lines[2] if len(lines) > 2 else ''

    # 资源
    out, _ = ssh_exec(host, "free -h | grep Mem | awk '{print $3\"/\"$2}'", user)
    result['memory'] = out

    out, _ = ssh_exec(host, "df -h / | tail -1 | awk '{print $3\"/\"$2\" \"$5}'", user)
    result['disk'] = out

    out, _ = ssh_exec(host, "cat /proc/loadavg | awk '{print $1}'", user)
    result['load'] = out

    # 服务
    services = {}
    for svc in ['nginx', 'mysql', 'pm2']:
        out, _ = ssh_exec(host, f"systemctl is-active {svc} 2>/dev/null || echo stopped", user)
        services[svc] = out
    result['services'] = services

    # Nginx站点
    out, _ = ssh_exec(host, "ls /etc/nginx/sites-enabled/ 2>/dev/null", user)
    result['nginx_sites'] = out.split('\n') if out else []

    return result

def cmd_exec(cmd, server='B'):
    """远程执行命令"""
    info = SERVERS.get(server, SERVERS['B'])
    out, code = ssh_exec(info['host'], cmd, info['user'])
    return {'status': 'ok' if code == 0 else 'error', 'output': out, 'exit_code': code}

def cmd_health(server='B'):
    """远程健康检查"""
    info = SERVERS.get(server, SERVERS['B'])
    host, user = info['host'], info['user']

    checks = {}

    # HTTP检查
    out, _ = ssh_exec(host, "curl -sk -o /dev/null -w '%{http_code}' --max-time 5 https://www.ttdazi.xyz/ 2>/dev/null", user)
    checks['https'] = out

    # Nginx状态
    out, _ = ssh_exec(host, "nginx -t 2>&1 | tail -1", user)
    checks['nginx_config'] = out

    # 磁盘
    out, _ = ssh_exec(host, "df -h / | tail -1 | awk '{print $5}' | tr -d '%'", user)
    checks['disk_pct'] = int(out) if out.isdigit() else 0

    # 连接数
    out, _ = ssh_exec(host, "ss -tn state established | wc -l", user)
    checks['connections'] = int(out) if out.isdigit() else 0

    return {'status': 'ok', 'server': server, 'checks': checks}

def cmd_all_status():
    """所有服务器状态"""
    results = {}
    for name, info in SERVERS.items():
        try:
            result = cmd_status(name)
            results[name] = result
        except Exception as e:
            results[name] = {'error': str(e)}

    return {'status': 'ok', 'servers': results}

def cmd_sync(local_path, remote_path='/tmp/', server='B'):
    """同步文件到远程"""
    info = SERVERS.get(server, SERVERS['B'])
    ok = scp_to(local_path, f"{info['user']}@{info['host']}:{remote_path}", info['host'], info['user'])
    return {'status': 'ok' if ok else 'error', 'file': local_path, 'dest': f"{info['host']}:{remote_path}"}

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    args = sys.argv[2:]

    if cmd == 'status':
        server = args[0] if args else 'B'
        result = cmd_status(server)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'exec' and args:
        server = args[1] if len(args) > 1 else 'B'
        result = cmd_exec(args[0], server)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'health':
        server = args[0] if args else 'B'
        result = cmd_health(server)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'all-status':
        result = cmd_all_status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'sync' and args:
        result = cmd_sync(args[0], args[1] if len(args) > 1 else '/tmp/')
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('用法: status|health|exec|all-status|sync')
