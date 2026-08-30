#!/usr/bin/env python3
"""
preventive — 预防性运维模块
在问题发生前主动处理：磁盘预测清理、SSL自动续签、服务健康预检

用法:
  python3 /opt/ttdazi/ops/preventive.py check     # 全面预检
  python3 /opt/ttdazi/ops/preventive.py disk       # 磁盘预测+预防清理
  python3 /opt/ttdazi/ops/preventive.py ssl         # SSL到期预防
  python3 /opt/ttdazi/ops/preventive.py service     # 服务健康预防

原理: 基于intelligence.py的预测数据，在问题发生前采取行动
"""
import os
import shlex
import sys
import json
import subprocess
import glob
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
DATA_DIR = BASE_DIR / 'data'
sys.path.insert(0, str(BASE_DIR))

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except:
        return '', -1

def load_predictions():
    """加载趋势预测数据"""
    pred_file = DATA_DIR / 'predictions.json'
    if pred_file.exists():
        return json.loads(pred_file.read_text())
    return {}

def load_baselines():
    """加载基线数据"""
    bl_file = DATA_DIR / 'baselines.json'
    if bl_file.exists():
        return json.loads(bl_file.read_text())
    return {}

# ═══════════════════════════════════════════
# 1. 磁盘预测 + 预防清理
# ═══════════════════════════════════════════

def check_disk_preventive():
    """基于预测数据，提前清理磁盘"""
    actions = []
    predictions = load_predictions()

    for mount in ['/', '/data/disk']:
        # 获取当前使用率
        out, _ = run(f"df {mount} | tail -1 | awk '{{print $5}}' | tr -d '%'")
        try:
            current_pct = int(out)
        except:
            continue

        # 获取预测数据
        pred_key = 'disk_root' if mount == '/' else 'disk_data'
        pred = predictions.get(pred_key, {})
        days_to_full = pred.get('days_to_full') or pred.get('days_to_100')
        daily_growth = pred.get('daily_growth', 0)

        action = {
            'mount': mount,
            'current_pct': current_pct,
            'daily_growth': daily_growth,
            'days_to_full': days_to_full,
            'action': 'none',
        }

        # 决策逻辑
        if current_pct >= 90:
            # 紧急：立即清理
            freed = emergency_cleanup(mount)
            action['action'] = 'emergency_cleanup'
            action['freed_mb'] = freed
            actions.append(action)
        elif current_pct >= 80:
            # 警告：预防性清理
            freed = preventive_cleanup(mount)
            action['action'] = 'preventive_cleanup'
            action['freed_mb'] = freed
            actions.append(action)
        elif days_to_full and days_to_full < 30:
            # 预测30天内撑满：轻度清理
            freed = light_cleanup(mount)
            action['action'] = 'light_cleanup'
            action['freed_mb'] = freed
            action['reason'] = f'预测{days_to_full:.0f}天后撑满'
            actions.append(action)
        else:
            action['action'] = 'ok'

    return actions

def emergency_cleanup(mount):
    """紧急清理：删最旧的备份+tmp+日志"""
    freed = 0
    # 删最旧的备份
    backups = sorted(glob.glob(f'/data/disk/daily_*'))
    for b in backups[:5]:
        try:
            size = sum(os.path.getsize(os.path.join(b, f)) for f in os.listdir(b) if os.path.isfile(os.path.join(b, f)))
            import shutil
            shutil.rmtree(b)
            freed += size
        except:
            pass

    # 删tmp
    for f in glob.glob('/tmp/ttdazi_*'):
        try:
            size = os.path.getsize(f) if os.path.isfile(f) else 0
            os.remove(f) if os.path.isfile(f) else None
            freed += size
        except:
            pass

    # 截断大日志
    for log in ['/var/log/ttdazi_monitor.log', '/var/log/auth.log']:
        try:
            size = os.path.getsize(log)
            if size > 10 * 1024 * 1024:  # >10MB
                run(f"sudo truncate -s 1M {log}")
                freed += size - 1024 * 1024
        except:
            pass

    return freed // 1024 // 1024  # MB

def preventive_cleanup(mount):
    """预防性清理：删过期备份+旧日志"""
    freed = 0
    # 删15天前的备份
    cutoff = (datetime.now() - timedelta(days=15)).timestamp()
    for b in sorted(glob.glob('/data/disk/daily_*')):
        try:
            if os.path.getmtime(b) < cutoff:
                size = sum(os.path.getsize(os.path.join(b, f)) for f in os.listdir(b) if os.path.isfile(os.path.join(b, f)))
                import shutil
                shutil.rmtree(b)
                freed += size
        except:
            pass

    # 删30天前的日志
    for log in glob.glob('/var/log/ttdazi_*.log'):
        try:
            if os.path.getmtime(log) < cutoff:
                size = os.path.getsize(log)
                os.remove(log)
                freed += size
        except:
            pass

    return freed // 1024 // 1024

def light_cleanup(mount):
    """轻度清理：只清理tmp和压缩旧日志"""
    freed = 0
    for f in glob.glob('/tmp/ttdazi_*'):
        try:
            if os.path.getmtime(f) < (datetime.now() - timedelta(days=7)).timestamp():
                size = os.path.getsize(f) if os.path.isfile(f) else 0
                os.remove(f) if os.path.isfile(f) else None
                freed += size
        except:
            pass
    return freed // 1024 // 1024

# ═══════════════════════════════════════════
# 2. SSL到期预防
# ═══════════════════════════════════════════

def check_ssl_preventive():
    """SSL证书到期预防：提前14天自动续签"""
    actions = []
    hosts = ['www.ttdazi.xyz', 'aiweb.openai2000.cn', 'pay.openai2000.cn', 'www.openai2000.cn']

    for host in hosts:
        out, _ = run(f"echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2")
        if not out:
            actions.append({'host': host, 'action': 'error', 'reason': '无法获取证书'})
            continue

        try:
            from email.utils import parsedate_to_datetime
            exp = parsedate_to_datetime(out)
            days_left = (exp - datetime.now(exp.tzinfo)).days
        except:
            actions.append({'host': host, 'action': 'error', 'reason': '解析失败'})
            continue

        action = {'host': host, 'days_left': days_left, 'action': 'none'}

        if days_left <= 7:
            # 紧急续签
            result = auto_renew_ssl(host)
            action['action'] = 'auto_renew'
            action['result'] = result
        elif days_left <= 14:
            # 尝试续签
            result = try_renew_ssl(host)
            action['action'] = 'try_renew'
            action['result'] = result
        else:
            action['action'] = 'ok'

        actions.append(action)

    return actions

def auto_renew_ssl(host):
    """自动续签SSL证书"""
    # 获取证书配置
    cert_name = host.replace('www.', '')
    out, code = run(f"sudo certbot renew --cert-name {cert_name} --quiet 2>&1", timeout=60)
    if code == 0:
        run("sudo systemctl reload nginx 2>/dev/null || sudo systemctl reload caddy 2>/dev/null")
        return f'续签成功: {out[:100]}'
    return f'续签失败: {out[:100]}'

def try_renew_ssl(host):
    """尝试续签（dry-run）"""
    cert_name = host.replace('www.', '')
    out, code = run(f"sudo certbot renew --cert-name {cert_name} --dry-run --quiet 2>&1", timeout=60)
    return 'dry-run成功' if code == 0 else f'dry-run失败: {out[:100]}'

# ═══════════════════════════════════════════
# 3. 服务健康预防
# ═══════════════════════════════════════════

def check_service_preventive():
    """服务健康预防：检测异常趋势，提前干预"""
    actions = []
    baselines = load_baselines()

    # 检查MySQL连接数趋势
    mysql_bl = baselines.get('mysql_conn', {})
    if mysql_bl:
        current_out, _ = run("mysql -uroot -p" + shlex.quote(os.environ.get('MYSQL_PASSWORD', '')) + " -N -e \"SHOW STATUS LIKE 'Threads_connected';\" | awk '{print $2}'")
        try:
            current = int(current_out)
            ewma = mysql_bl.get('ewma', 0)
            upper = mysql_bl.get('upper', 100)

            if current > upper * 0.8:
                actions.append({
                    'service': 'mysql',
                    'action': 'warn',
                    'reason': f'连接数{current}接近上限{upper}',
                    'current': current,
                    'threshold': upper
                })
        except:
            pass

    # 检查内存趋势
    mem_bl = baselines.get('mem', {})
    if mem_bl:
        out, _ = run("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
        try:
            current_mem = float(out)
            upper_mem = mem_bl.get('upper', 90)

            if current_mem > upper_mem * 0.85:
                actions.append({
                    'service': 'memory',
                    'action': 'warn',
                    'reason': f'内存使用{current_mem}%接近警戒线',
                    'current': current_mem,
                    'threshold': upper_mem
                })
        except:
            pass

    # 检查进程数异常
    out, _ = run("ps aux | wc -l")
    try:
        proc_count = int(out) - 1
        if proc_count > 300:
            actions.append({
                'service': 'processes',
                'action': 'warn',
                'reason': f'进程数{proc_count}异常偏高',
                'current': proc_count,
                'threshold': 300
            })
    except:
        pass

    # 检查僵尸进程
    out, _ = run("ps aux | awk '$8 ~ /Z/ {print $2, $11}' | head -5")
    if out.strip():
        actions.append({
            'service': 'zombie',
            'action': 'warn',
            'reason': f'发现僵尸进程',
            'details': out[:200]
        })

    if not actions:
        actions.append({'service': 'all', 'action': 'ok'})

    return actions

# ═══════════════════════════════════════════
# 综合预检
# ═══════════════════════════════════════════

def full_check():
    """全面预防性预检"""
    result = {
        'timestamp': datetime.now().isoformat(),
        'disk': check_disk_preventive(),
        'ssl': check_ssl_preventive(),
        'service': check_service_preventive(),
    }

    # 统计
    actions_taken = 0
    for section in ['disk', 'ssl', 'service']:
        for item in result[section]:
            if item.get('action') not in ('none', 'ok', 'error'):
                actions_taken += 1

    result['summary'] = {
        'actions_taken': actions_taken,
        'disk_ok': all(a['action'] == 'ok' for a in result['disk']),
        'ssl_ok': all(a['action'] == 'ok' for a in result['ssl']),
        'service_ok': all(a['action'] in ('ok',) for a in result['service']),
    }

    return result

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == 'check':
        result = full_check()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'disk':
        result = check_disk_preventive()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'ssl':
        result = check_ssl_preventive()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'service':
        result = check_service_preventive()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f'未知命令: {cmd}')
