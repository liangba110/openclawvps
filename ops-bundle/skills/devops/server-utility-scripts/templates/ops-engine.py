#!/usr/bin/env python3
"""
Ops自治引擎 — YAML规则驱动的自动检测+自动修复
用法:
  单次执行: python3 engine.py
  守护模式: python3 engine.py --daemon [间隔秒数]
  测试单条: python3 engine.py --rule services.yaml
  查看状态: python3 engine.py --status

原理: 读YAML规则 → 执行check → 满足条件则执行actions → 只在升级时通知Hermes
"""
import os, sys, json, time, subprocess
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyyaml', '-q'])
    import yaml

BASE_DIR = Path('/opt/ttdazi/ops')
RULES_DIR = BASE_DIR / 'rules'
STATE_DIR = BASE_DIR / 'state'
LOGS_DIR = BASE_DIR / 'logs'

for d in [STATE_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ═══ 状态管理 ═══
def load_state(name):
    path = STATE_DIR / f'{name}.json'
    if path.exists():
        try: return json.loads(path.read_text())
        except: return {}
    return {}

def save_state(name, data):
    (STATE_DIR / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1))

def get_counter(rule_name):
    state = load_state('counters')
    return state.get(rule_name, {'count': 0, 'last_trigger': None, 'last_action': None})

def increment_counter(rule_name, action_taken=False):
    state = load_state('counters')
    if rule_name not in state:
        state[rule_name] = {'count': 0, 'last_trigger': None, 'last_action': None}
    state[rule_name]['count'] += 1
    state[rule_name]['last_trigger'] = datetime.now().isoformat()
    if action_taken:
        state[rule_name]['last_action'] = datetime.now().isoformat()
    save_state('counters', state)

def reset_counter(rule_name):
    state = load_state('counters')
    if rule_name in state: state[rule_name]['count'] = 0
    save_state('counters', state)

# ═══ 命令执行 ═══
def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except: return '', -1

# ═══ Check 执行器 ═══
def check_http(cfg):
    cmd = f"curl -sk -o /dev/null -w '%{{http_code}}' --max-time {cfg.get('timeout',5)} {cfg['url']}"
    output, _ = run_cmd(cmd, cfg.get('timeout',5) + 5)
    try: http_code = int(output)
    except: http_code = 0
    expected = cfg.get('expected_code', 200)
    return {'pass': http_code == expected, 'value': http_code, 'detail': f'HTTP {http_code}'}

def check_command(cfg):
    output, code = run_cmd(cfg['cmd'], cfg.get('timeout', 30))
    threshold = cfg.get('threshold')
    if threshold is None:
        return {'pass': code == 0, 'value': output, 'detail': output[:200]}
    try:
        value, threshold = float(output), float(threshold)
    except ValueError:
        return {'pass': False, 'value': output, 'detail': f'无法解析: {output[:100]}'}
    ops = {'>': lambda a,b: a>b, '>=': lambda a,b: a>=b, '<': lambda a,b: a<b,
           '<=': lambda a,b: a<=b, '==': lambda a,b: a==b, '!=': lambda a,b: a!=b}
    op_func = ops.get(cfg.get('operator','=='), ops['=='])
    triggered = op_func(value, threshold)
    return {'pass': not triggered, 'value': value, 'threshold': threshold,
            'detail': f'{value} {cfg.get("operator",">=")} {threshold} → {"ALERT" if triggered else "OK"}'}

def check_disk(cfg):
    results = []
    worst = 'ok'
    for path in cfg.get('paths', ['/']):
        output, _ = run_cmd(f"df {path} | tail -1 | awk '{{print $5}}' | tr -d '%'")
        try: pct = int(output)
        except: pct = 0
        status = 'critical' if pct >= cfg.get('critical_threshold',90) else ('warn' if pct >= cfg.get('warn_threshold',80) else 'ok')
        if status == 'critical': worst = 'critical'
        elif status == 'warn' and worst != 'critical': worst = 'warn'
        results.append({'path': path, 'percent': pct, 'status': status})
    return {'pass': worst == 'ok', 'status': worst, 'detail': ' | '.join(f"{r['path']}:{r['percent']}%" for r in results)}

def check_systemd(cfg):
    output, _ = run_cmd(f"systemctl is-active {cfg['service']}")
    return {'pass': output == 'active', 'value': output, 'detail': f'{cfg["service"]}: {output}'}

def check_ssl(cfg):
    results = []
    for host in cfg.get('hosts', []):
        output, _ = run_cmd(f"echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2", 10)
        if output:
            try:
                from email.utils import parsedate_to_datetime
                exp = parsedate_to_datetime(output)
                days = (exp - datetime.now(exp.tzinfo)).days
                results.append({'host': host, 'days_left': days})
            except: results.append({'host': host, 'days_left': -1})
        else: results.append({'host': host, 'days_left': -1})
    expired = [r for r in results if r['days_left'] <= cfg.get('warn_days', 14)]
    return {'pass': len(expired) == 0, 'detail': f'{len(expired)}个证书即将到期' if expired else '全部正常'}

CHECKERS = {'http': check_http, 'command': check_command, 'disk_usage': check_disk,
            'systemd': check_systemd, 'ssl': check_ssl}

# ═══ Action 执行器 ═══
def action_restart(cfg):
    run_cmd(f"sudo systemctl restart {cfg['service']}", 30)
    time.sleep(2)
    output, _ = run_cmd(f"systemctl is-active {cfg['service']}")
    return {'success': output == 'active', 'detail': f'{cfg["service"]}: {output}'}

def action_cleanup(cfg):
    import glob as g, shutil
    cleaned, freed = 0, 0
    for t in cfg.get('targets', []):
        cutoff = time.time() - t.get('keep_days', 15) * 86400
        for p in sorted(g.glob(t['pattern'])):
            if os.path.exists(p) and os.path.getmtime(p) < cutoff:
                try:
                    sz = os.path.getsize(p) if os.path.isfile(p) else 0
                    os.remove(p) if os.path.isfile(p) else shutil.rmtree(p)
                    cleaned += 1; freed += sz
                except: pass
    return {'success': True, 'detail': f'清理{cleaned}项，释放{freed/1024/1024:.1f}MB'}

def action_notify(cfg, check_result, rule_name):
    msg = cfg.get('message', 'Ops告警')
    for k, v in (check_result if isinstance(check_result, dict) else {}).items():
        if isinstance(v, (str, int, float)): msg = msg.replace('{' + k + '}', str(v))
    esc = load_state('escalation')
    esc.setdefault('pending', []).append({'timestamp': datetime.now().isoformat(), 'severity': cfg.get('severity','warn'), 'message': msg})
    esc['pending'] = esc['pending'][-20:]
    save_state('escalation', esc)
    return {'success': True}

ACTIONERS = {'restart_systemd': action_restart, 'cleanup': action_cleanup, 'notify': action_notify}

# ═══ 规则引擎 ═══
def execute_rule(rule):
    name = rule.get('name', 'unnamed')
    check_cfg = rule.get('check', {})
    check_type = check_cfg.get('type', 'command')
    checker = CHECKERS.get(check_type)
    if not checker:
        return {'name': name, 'status': 'error', 'error': f'未知check类型: {check_type}'}
    check_result = checker(check_cfg)
    if check_result.get('pass', False):
        reset_counter(name)
        return {'name': name, 'status': 'ok', 'check': check_result}
    increment_counter(name)
    actions_taken = []
    for action_cfg in rule.get('actions', []):
        actioner = ACTIONERS.get(action_cfg.get('type'))
        if actioner:
            try:
                if action_cfg.get('type') == 'notify':
                    result = actioner(action_cfg, check_result, name)
                else: result = actioner(action_cfg)
                actions_taken.append({'type': action_cfg['type'], 'result': result})
            except Exception as e:
                actions_taken.append({'type': action_cfg['type'], 'error': str(e)})
    return {'name': name, 'status': 'actioned', 'check': check_result, 'actions_taken': actions_taken}

def load_rules(rule_file=None):
    rules = []
    files = [RULES_DIR / rule_file] if rule_file else sorted(RULES_DIR.glob('*.yaml'))
    for f in files:
        if f.exists():
            try:
                data = yaml.safe_load(f.read_text())
                if isinstance(data, list): rules.extend(data)
            except Exception as e: print(f"⚠️ {f.name}: {e}", file=sys.stderr)
    return rules

def run_once(rule_file=None):
    rules = load_rules(rule_file)
    results = [execute_rule(r) for r in rules]
    ok = sum(1 for r in results if r['status'] == 'ok')
    act = sum(1 for r in results if r['status'] == 'actioned')
    err = sum(1 for r in results if r['status'] == 'error')
    ts = datetime.now().strftime('%H:%M:%S')
    if act or err:
        print(f"[{ts}] 🔔 {len(results)}条规则: ✅{ok} 🔧{act} ❌{err}")
        for r in results:
            if r['status'] != 'ok':
                print(f"  {'🔧' if r['status']=='actioned' else '❌'} {r['name']}: {r.get('check',{}).get('detail', r.get('error',''))}")
    else:
        print(f"[{ts}] ✅ {len(results)}条规则全部正常")
    summary = {'timestamp': datetime.now().isoformat(), 'total': len(results), 'ok': ok, 'actioned': act, 'error': err, 'details': results}
    sf = LOGS_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    sf.write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    for old in sorted(LOGS_DIR.glob('summary_*.json'))[:-50]: old.unlink()
    return summary

def daemon_mode(interval=60):
    import signal
    print(f"🛡️ Ops自治引擎已启动 (PID={os.getpid()})")
    running = True
    def handler(sig, frame): nonlocal running; running = False
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)
    while running:
        try: run_once()
        except Exception as e: print(f"⚠️ {e}", file=sys.stderr)
        for _ in range(interval):
            if not running: break
            time.sleep(1)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--daemon': daemon_mode(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
        elif sys.argv[1] == '--rule': run_once(sys.argv[2] if len(sys.argv) > 2 else None)
        elif sys.argv[1] == '--status':
            c = load_state('counters'); e = load_state('escalation')
            print(f"📊 规则: {len(load_rules())} | 计数器: {len(c)} | 待处理: {len(e.get('pending',[]))}")
        else: print("用法: [--daemon [秒]] [--rule 文件] [--status]")
    else: run_once()
