#!/usr/bin/env python3
"""
Ops自治引擎 — YAML规则驱动的自动检测+自动修复
用法:
  单次执行: python3 /opt/ttdazi/ops/engine.py
  守护模式: python3 /opt/ttdazi/ops/engine.py --daemon
  测试单条: python3 /opt/ttdazi/ops/engine.py --rule services.yaml

原理: 读YAML规则 → 执行check → 满足条件则执行actions → 只在升级时通知Hermes
"""
import os
import sys
import json
import time
import yaml
import subprocess
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from event_bus import bus
from self_learning import learner
from predictive import predictor
from multi_agent import orchestrator

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
RULES_DIR = BASE_DIR / 'rules'
STATE_DIR = BASE_DIR / 'state'
LOGS_DIR = BASE_DIR / 'logs'

# 确保目录存在
for d in [STATE_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════
# 状态管理
# ═══════════════════════════════════════════

def load_state(name):
    """加载状态文件"""
    path = STATE_DIR / f'{name}.json'
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}

def save_state(name, data):
    """保存状态文件（带文件锁防并发）"""
    import fcntl
    path = STATE_DIR / f'{name}.json'
    try:
        with open(path, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(data, ensure_ascii=False, indent=1))
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1))

def get_counter(rule_name):
    """获取规则触发计数"""
    state = load_state('counters')
    return state.get(rule_name, {'count': 0, 'last_trigger': None, 'last_action': None})

def increment_counter(rule_name, action_taken=False):
    """增加计数"""
    state = load_state('counters')
    if rule_name not in state:
        state[rule_name] = {'count': 0, 'last_trigger': None, 'last_action': None}
    state[rule_name]['count'] += 1
    state[rule_name]['last_trigger'] = datetime.now().isoformat()
    if action_taken:
        state[rule_name]['last_action'] = datetime.now().isoformat()
    save_state('counters', state)

def reset_counter(rule_name):
    """重置计数"""
    state = load_state('counters')
    if rule_name in state:
        state[rule_name]['count'] = 0
    save_state('counters', state)

def check_cooldown(rule_name, cooldown_seconds):
    """检查冷却时间"""
    counter = get_counter(rule_name)
    if counter.get('last_action'):
        last = datetime.fromisoformat(counter['last_action'])
        if (datetime.now() - last).total_seconds() < cooldown_seconds:
            return False  # 还在冷却中
    return True

# ═══════════════════════════════════════════
# Check 执行器
# ═══════════════════════════════════════════

def run_cmd(cmd, timeout=30):
    """执行命令"""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return '', -1
    except Exception as e:
        return str(e), -1

def check_http(cfg):
    """HTTP健康检查"""
    url = cfg['url']
    timeout = cfg.get('timeout', 5)
    expected = cfg.get('expected_code', 200)
    cmd = f"curl -sk -o /dev/null -w '%{{http_code}}' --max-time {timeout} {url}"
    output, code = run_cmd(cmd, timeout + 5)
    try:
        http_code = int(output)
    except ValueError:
        http_code = 0
    ok = http_code == expected
    return {
        'pass': ok,
        'value': http_code,
        'expected': expected,
        'detail': f'HTTP {http_code}' if ok else f'HTTP {http_code} (expected {expected})'
    }

def check_command(cfg):
    """命令检查"""
    cmd = cfg['cmd']
    threshold = cfg.get('threshold')
    operator = cfg.get('operator', '==')
    timeout = cfg.get('timeout', 30)
    
    output, code = run_cmd(cmd, timeout)
    
    if threshold is None:
        return {'pass': code == 0, 'value': output, 'detail': output[:200]}
    
    try:
        value = float(output)
        threshold = float(threshold)
    except ValueError:
        return {'pass': False, 'value': output, 'detail': f'无法解析数值: {output[:100]}'}
    
    ops = {
        '>': lambda a, b: a > b,
        '>=': lambda a, b: a >= b,
        '<': lambda a, b: a < b,
        '<=': lambda a, b: a <= b,
        '==': lambda a, b: a == b,
        '!=': lambda a, b: a != b,
    }
    
    op_func = ops.get(operator, ops['=='])
    # 反转逻辑：条件满足=有问题(fail)，条件不满足=正常(pass)
    triggered = op_func(value, threshold)
    
    return {
        'pass': not triggered,
        'value': value,
        'threshold': threshold,
        'operator': operator,
        'detail': f'{value} {operator} {threshold} → {"ALERT" if triggered else "OK"}'
    }

def check_disk(cfg):
    """磁盘使用检查"""
    paths = cfg.get('paths', ['/'])
    warn = cfg.get('warn_threshold', 80)
    crit = cfg.get('critical_threshold', 90)
    
    results = []
    worst_status = 'ok'
    
    for path in paths:
        cmd = f"df {path} | tail -1 | awk '{{print $5}}' | tr -d '%'"
        output, _ = run_cmd(cmd)
        try:
            pct = int(output)
        except ValueError:
            pct = 0
        
        status = 'ok'
        if pct >= crit:
            status = 'critical'
            worst_status = 'critical'
        elif pct >= warn:
            status = 'warn'
            if worst_status != 'critical':
                worst_status = 'warn'
        
        results.append({'path': path, 'percent': pct, 'status': status})
    
    return {
        'pass': worst_status == 'ok',
        'status': worst_status,
        'disks': results,
        'detail': ' | '.join(f"{r['path']}:{r['percent']}%" for r in results)
    }

def check_systemd(cfg):
    """systemd服务检查"""
    service = cfg['service']
    cmd = f"systemctl is-active {service}"
    output, code = run_cmd(cmd)
    alive = output == 'active'
    
    return {
        'pass': alive,
        'value': output,
        'detail': f'{service}: {output}'
    }

def check_ssl(cfg):
    """SSL证书到期检查"""
    hosts = cfg.get('hosts', [])
    warn_days = cfg.get('warn_days', 14)
    
    results = []
    for host in hosts:
        cmd = f"echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2"
        output, _ = run_cmd(cmd, timeout=10)
        
        if output:
            try:
                from email.utils import parsedate_to_datetime
                exp_date = parsedate_to_datetime(output)
                days_left = (exp_date - datetime.now(exp_date.tzinfo)).days
                results.append({'host': host, 'days_left': days_left, 'expire': output})
            except Exception:
                results.append({'host': host, 'days_left': -1, 'expire': 'parse_error'})
        else:
            results.append({'host': host, 'days_left': -1, 'expire': 'connect_failed'})
    
    expired = [r for r in results if r['days_left'] <= warn_days]
    return {
        'pass': len(expired) == 0,
        'hosts': results,
        'expiring': expired,
        'detail': f'{len(expired)}个证书将在{warn_days}天内到期' if expired else '全部正常'
    }

# Check类型映射
CHECKERS = {
    'http': check_http,
    'command': check_command,
    'disk_usage': check_disk,
    'systemd': check_systemd,
    'ssl': check_ssl,
}

def check_preventive(cfg):
    """预防性运维检查"""
    try:
        import sys as _sys
        _sys.path.insert(0, os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
        from preventive import full_check
        result = full_check()
        issues = []
        for section in ['disk', 'ssl', 'service']:
            for item in result.get(section, []):
                if item.get('action') not in ('ok', 'none', 'error'):
                    issues.append(f"{item.get('service', item.get('host', item.get('mount', '?')))}: {item.get('action')}")
        return {'pass': len(issues) == 0, 'issues': issues, 'detail': f'{len(issues)}个预防性问题' if issues else '全部正常'}
    except Exception as e:
        return {'pass': True, 'detail': f'预防检查异常: {str(e)[:50]}'}

CHECKERS['preventive'] = check_preventive


def check_anomaly(cfg):
    """基于EWMA基线的智能异常检测"""
    baselines_path = Path('/opt/ttdazi/ops/data/baselines.json')
    if not baselines_path.exists():
        return {'pass': True, 'detail': '无基线数据，跳过异常检测'}
    
    baselines = json.loads(baselines_path.read_text())
    metrics_to_check = cfg.get('metrics', ['cpu', 'mem', 'connections'])
    
    anomalies = []
    for metric in metrics_to_check:
        if metric not in baselines:
            continue
        
        bl = baselines[metric]
        # 获取当前值
        cmd_map = {
            'cpu': "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
            'mem': "free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'",
            'connections': "ss -tn state established | wc -l",
            'mysql_conn': "mysql -uroot -p'" + os.environ.get('MYSQL_PASSWORD', '') + "' -N -e \"SHOW STATUS LIKE 'Threads_connected';\" 2>/dev/null | awk '{print $2}'",
            'load': "cat /proc/loadavg | awk '{print $1}'",
        }
        
        if metric in cmd_map:
            output, _ = run_cmd(cmd_map[metric])
            try:
                value = float(output)
            except:
                continue
            
            ewma = bl['ewma']
            std = bl['std']
            upper = bl['upper']
            
            if std > 0 and value > upper:
                z_score = (value - ewma) / std
                anomalies.append({
                    'metric': metric,
                    'value': value,
                    'baseline': ewma,
                    'z_score': round(z_score, 2),
                    'detail': f'{metric}={value} 超出基线(μ={ewma:.1f}, σ={std:.1f}, z={z_score:.1f})'
                })
    
    if anomalies:
        return {
            'pass': False,
            'anomalies': anomalies,
            'detail': f'{len(anomalies)}个指标异常'
        }
    
    return {'pass': True, 'detail': '所有指标在基线范围内'}

# 添加到Checkers

CHECKERS['anomaly'] = check_anomaly

# ═══════════════════════════════════════════
# Action 执行器
# ═══════════════════════════════════════════

def action_restart_service(cfg):
    """重启服务"""
    service = cfg['service']
    cmd = f"sudo systemctl restart {service}"
    output, code = run_cmd(cmd, timeout=30)
    
    # 验证重启后状态
    time.sleep(2)
    status_cmd = f"systemctl is-active {service}"
    status, _ = run_cmd(status_cmd)
    
    return {
        'success': status == 'active',
        'detail': f'restart {service}: {status}',
        'service': service
    }

def action_cleanup_files(cfg):
    """清理文件"""
    import glob as glob_mod
    targets = cfg.get('targets', [])
    total_freed = 0
    total_cleaned = 0
    
    for target in targets:
        pattern = target['pattern']
        keep_days = target.get('keep_days', 15)
        cutoff = time.time() - keep_days * 86400
        
        for path in sorted(glob_mod.glob(pattern)):
            if not os.path.exists(path):
                continue
            mtime = os.path.getmtime(path)
            if mtime < cutoff:
                try:
                    size = os.path.getsize(path) if os.path.isfile(path) else 0
                    if os.path.isfile(path):
                        os.remove(path)
                    elif os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path)
                    total_cleaned += 1
                    total_freed += size
                except Exception:
                    pass
    
    return {
        'success': True,
        'cleaned': total_cleaned,
        'freed_bytes': total_freed,
        'detail': f'清理{total_cleaned}项，释放{total_freed / 1024 / 1024:.1f}MB'
    }

def action_block_ip(cfg):
    """封禁IP（带白名单保护）"""
    count = cfg.get('count', 10)
    
    # 白名单：永不封禁的IP
    WHITELIST = ['127.0.0.1', '::1', '42.193.113.230', '82.157.202.24', '165.154.224.225', '185.239.224.191']
    
    # 获取Top爆破IP
    cmd = f"grep 'Failed password' /var/log/auth.log 2>/dev/null | grep -oE 'from [0-9.]+' | awk '{{print $2}}' | sort | uniq -c | sort -rn | head -{count}"
    output, _ = run_cmd(cmd)
    
    blocked = 0
    for line in output.split('\n'):
        if line.strip():
            parts = line.strip().split()
            if len(parts) == 2:
                ip = parts[1]
                if ip in WHITELIST:
                    continue  # 跳过白名单IP
                try:
                    run_cmd(f"sudo iptables -A INPUT -s {ip} -j DROP")
                    blocked += 1
                except Exception:
                    pass
    
    return {
        'success': blocked > 0,
        'blocked_count': blocked,
        'detail': f'封禁{blocked}个IP'
    }

def action_optimize_db(cfg):
    """优化数据库"""
    tables = cfg.get('tables', [])
    database = cfg.get('database', 'huizhiyun')
    
    optimized = []
    for table in tables:
        cmd = f"mysql -uroot -p'" + os.environ.get('MYSQL_PASSWORD', '') + "' {database} -e 'OPTIMIZE TABLE `{table}`;' 2>/dev/null"
        output, code = run_cmd(cmd, timeout=120)
        if code == 0:
            optimized.append(table)
    
    return {
        'success': len(optimized) > 0,
        'optimized': optimized,
        'detail': f'优化{len(optimized)}个表'
    }

def action_notify(cfg, check_result, action_result):
    """通知 — 使用alerts模块（带去重+静默）"""
    message = cfg.get('message', 'Ops告警')
    severity = cfg.get('severity', 'warn')
    
    # 变量替换
    if isinstance(check_result, dict):
        for k, v in check_result.items():
            if isinstance(v, (str, int, float)):
                message = message.replace('{' + k + '}', str(v))
    if isinstance(action_result, dict):
        for k, v in action_result.items():
            if isinstance(v, (str, int, float)):
                message = message.replace('{' + k + '}', str(v))
    
    # 使用alerts模块（带静默去重）
    try:
        sys.path.insert(0, os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
        from alerts import send_alert
        # 用消息前30字作为静默key，防止重复推送
        suppress_key = message[:30]
        send_alert(message, level=severity, source='engine', channel='all', suppress_key=suppress_key)
    except Exception:
        # fallback: 直接写escalation
        escalation = load_state('escalation')
        if 'pending' not in escalation:
            escalation['pending'] = []
        escalation['pending'].append({
            'timestamp': datetime.now().isoformat(),
            'severity': severity,
            'message': message
        })
        escalation['pending'] = escalation['pending'][-20:]
        save_state('escalation', escalation)
    
    return {'success': True, 'detail': f'已升级: {message[:80]}'}

def action_log_event(cfg, check_result, rule_name):
    """记录事件日志"""
    severity = cfg.get('severity', 'info')
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'rule': rule_name,
        'severity': severity,
        'check': check_result
    }
    
    # 追加到日志文件
    log_file = LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with open(log_file, 'a') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    return {'success': True}

# Action类型映射
ACTIONERS = {
    'restart_systemd': action_restart_service,
    'cleanup': action_cleanup_files,
    'block_ip_top': action_block_ip,
    'optimize_db': action_optimize_db,
    'notify': action_notify,
    'log_event': action_log_event,
}

# ═══════════════════════════════════════════
# 规则引擎
# ═══════════════════════════════════════════

def evaluate_check(check_cfg):
    """执行检查"""
    check_type = check_cfg.get('type', 'command')
    checker = CHECKERS.get(check_type)
    if not checker:
        return {'pass': False, 'detail': f'未知check类型: {check_type}'}
    return checker(check_cfg)

def should_execute_action(action_cfg, check_result, rule_name):
    """判断是否应该执行动作"""
    when = action_cfg.get('when', 'always')
    
    if when == 'always':
        return True
    elif when == 'on_fail':
        return not check_result.get('pass', True)
    elif when == 'on_success':
        return check_result.get('pass', True)
    elif when.startswith('>='):
        try:
            threshold = int(when.replace('>=', '').replace('%', ''))
            return check_result.get('status') in ('warn', 'critical')
        except ValueError:
            return True
    
    # 冷却检查
    cooldown = action_cfg.get('cooldown', 0)
    if cooldown > 0 and not check_cooldown(rule_name, cooldown):
        return False
    
    # 最大重试检查
    max_retries = action_cfg.get('max_retries', 999)
    counter = get_counter(rule_name)
    if counter['count'] >= max_retries:
        # 超过最大重试，升级
        if action_cfg.get('on_failure') == 'escalate':
            return True  # 升级动作仍然执行
        return False
    
    return True

def execute_rule(rule):
    """执行单条规则"""
    name = rule.get('name', 'unnamed')
    check_cfg = rule.get('check', {})
    actions = rule.get('actions', [])
    
    # 执行检查
    check_result = evaluate_check(check_cfg)
    
    passed = check_result.get('pass', False)
    
    if passed:
        # 检查通过，重置计数
        reset_counter(name)
        return {
            'name': name,
            'status': 'ok',
            'check': check_result,
            'actions_taken': []
        }
    
    # 检查失败，执行动作
    increment_counter(name)
    actions_taken = []
    
    for action_cfg in actions:
        action_type = action_cfg.get('type', 'log_event')
        
        if not should_execute_action(action_cfg, check_result, name):
            continue
        
        actioner = ACTIONERS.get(action_type)
        if not actioner:
            continue
        
        try:
            if action_type in ('notify', 'log_event'):
                result = actioner(action_cfg, check_result, name)
            else:
                result = actioner(action_cfg)
            
            actions_taken.append({
                'type': action_type,
                'result': result
            })
            
            # 冷却记录
            if action_cfg.get('cooldown', 0) > 0:
                increment_counter(name, action_taken=True)
                
        except Exception as e:
            actions_taken.append({
                'type': action_type,
                'error': str(e)
            })
    
    return {
        'name': name,
        'status': 'actioned',
        'check': check_result,
        'actions_taken': actions_taken
    }

def load_rules(rule_file=None):
    """加载规则"""
    rules = []
    if rule_file:
        files = [RULES_DIR / rule_file]
    else:
        files = sorted(RULES_DIR.glob('*.yaml'))
    
    for f in files:
        if f.exists():
            try:
                data = yaml.safe_load(f.read_text())
                if isinstance(data, list):
                    rules.extend(data)
            except Exception as e:
                print(f"⚠️ 加载{f.name}失败: {e}", file=sys.stderr)
    
    return rules

def run_once(rule_file=None):
    # 多Agent协作周期（每10次规则扫描执行一次）
    try:
        counter = load_state('agent_counter')
        count = counter.get('count', 0) + 1
        if count % 10 == 0:  # 每10次执行一次多Agent周期
            result = orchestrator.run_cycle()
            if result.get('status') == 'escalated':
                bus.emit('escalation', {'message': f"多Agent检测到{result.get('anomalies',0)}个异常需人工介入"})
        counter['count'] = count
        save_state('agent_counter', counter)
    except Exception:
        pass
    # 预测性检查（每次执行前）
    try:
        predictions = predictor.predict_issues()
        if predictions:
            auto_actions = predictor.auto_remediate(predictions)
            if auto_actions:
                for action in auto_actions:
                    bus.emit('predictive_action', {'action': action, 'timestamp': datetime.now().isoformat()})
    except Exception:
        pass
    """执行一次所有规则"""
    rules = load_rules(rule_file)
    results = []
    
    for rule in rules:
        try:
            result = execute_rule(rule)
            results.append(result)
        except Exception as e:
            results.append({
                'name': rule.get('name', 'unnamed'),
                'status': 'error',
                'error': str(e)
            })
    
    # 统计
    ok_count = sum(1 for r in results if r['status'] == 'ok')
    actioned_count = sum(1 for r in results if r['status'] == 'actioned')
    error_count = sum(1 for r in results if r['status'] == 'error')
    
    # 写入执行摘要
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total': len(results),
        'ok': ok_count,
        'actioned': actioned_count,
        'error': error_count,
        'details': results
    }
    
    summary_file = LOGS_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    
    # 只保留最近50个摘要
    summaries = sorted(LOGS_DIR.glob('summary_*.json'))
    for old in summaries[:-50]:
        old.unlink()
    
    # 持久化执行结果
    history_file = BASE_DIR / 'data' / 'execution_history.jsonl'
    try:
        with open(history_file, 'a') as f:
            f.write(json.dumps({
                'timestamp': datetime.now().isoformat(),
                'total': len(results),
                'ok': ok_count,
                'actioned': actioned_count,
                'error': error_count
            }) + '\n')
        # 只保留最近1000条
        lines = history_file.read_text().strip().split('\n')
        if len(lines) > 1000:
            history_file.write_text('\n'.join(lines[-1000:]) + '\n')
    except Exception:
        pass
    
    # 输出
    ts = datetime.now().strftime('%H:%M:%S')
    if actioned_count > 0 or error_count > 0:
        print(f"[{ts}] 🔔 {len(results)}条规则: ✅{ok_count} 🔧{actioned_count} ❌{error_count}")
        for r in results:
            if r['status'] != 'ok':
                detail = r.get('check', {}).get('detail', r.get('error', ''))
                print(f"  {'🔧' if r['status'] == 'actioned' else '❌'} {r['name']}: {detail}")
    else:
        print(f"[{ts}] ✅ {len(results)}条规则全部正常")
    
    return summary

def daemon_mode(interval=60):
    """守护模式"""
    print(f"🛡️ Ops自治引擎已启动 (PID={os.getpid()})")
    print(f"📋 规则目录: {RULES_DIR}")
    print(f"⏱️ 检测间隔: {interval}秒")
    
    import signal
    running = True
    def handle_signal(sig, frame):
        nonlocal running
        running = False
    
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    while running:
        try:
            run_once()
        except Exception as e:
            print(f"⚠️ 引擎异常: {e}", file=sys.stderr)
        
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

# ═══════════════════════════════════════════
# CLI入口
# ═══════════════════════════════════════════


if __name__ == '__main__':
    # 确保yaml可用
    try:
        import yaml
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyyaml', '-q'])
        import yaml
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--daemon':
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
            daemon_mode(interval)
        elif sys.argv[1] == '--rule':
            rule_file = sys.argv[2] if len(sys.argv) > 2 else None
            run_once(rule_file)
        elif sys.argv[1] == '--status':
            # 显示当前状态
            counters = load_state('counters')
            escalation = load_state('escalation')
            print("📊 Ops引擎状态:")
            print(f"  规则数: {len(load_rules())}")
            print(f"  活跃计数器: {len(counters)}")
            pending = escalation.get('pending', [])
            print(f"  待处理告警: {len(pending)}")
            for e in pending[-5:]:
                print(f"    [{e['severity']}] {e['message'][:80]}")
        else:
            print("用法:")
            print("  python3 engine.py              # 单次执行")
            print("  python3 engine.py --daemon     # 守护模式")
            print("  python3 engine.py --daemon 30  # 守护模式(30秒间隔)")
            print("  python3 engine.py --rule xxx.yaml  # 执行单个规则文件")
            print("  python3 engine.py --status     # 查看状态")
    else:
        run_once()




def action_llm_decide(cfg, check_result, action_result):
    """调用LLM分析复杂问题并给出决策"""
    try:
        import sys as _sys
        _sys.path.insert(0, os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
        from brain import decide
        issue = cfg.get('message', str(check_result))
        decision = decide(issue)
        
        # 安全命令白名单（只执行这些命令）
        SAFE_COMMANDS = ['systemctl', 'mysql', 'nginx', 'df', 'free', 'top', 'ps', 'ss', 'curl']
        if decision.get('actions') and decision.get('risk') in ('low', 'medium'):
            for action in decision['actions'][:2]:
                cmd = action.get('cmd', '')
                # 安全检查：只执行白名单内的命令
                if cmd and any(cmd.startswith(s) for s in SAFE_COMMANDS):
                    if 'rm -rf' not in cmd and 'DROP' not in cmd.upper() and 'DELETE' not in cmd.upper():
                        run_cmd(cmd, timeout=30)
        
        return {'success': True, 'detail': f'LLM决策: {decision.get("analysis", str(decision)[:100])}'}
    except Exception as e:
        return {'success': False, 'detail': 'LLM调用失败，请检查API配置'}


def action_create_ticket(cfg, check_result, action_result):
    """自动创建开发工单（引擎无法修复时）"""
    try:
        import sys as _sys
        _sys.path.insert(0, os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
        from devloop import create_ticket
        issue = cfg.get('message', str(check_result.get('detail', '')))
        severity = cfg.get('severity', 'warn')
        ticket = create_ticket(issue, source='engine', severity=severity)
        return {'success': True, 'detail': f'工单已创建: {ticket["id"]}'}
    except Exception as e:
        return {'success': False, 'detail': '工单创建失败，请检查配置'}

