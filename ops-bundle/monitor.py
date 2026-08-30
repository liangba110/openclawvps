#!/usr/bin/env python3
"""
monitor.py — 主动探测监控（替代被动轮询）
周期性检查关键服务，发现异常通过事件总线广播
"""
import os
import sys
import json
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from event_bus import bus

DATA_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops')) / 'data'
STATE_FILE = DATA_DIR / 'monitor_state.json'

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except:
        return '', -1

class ServiceMonitor:
    """服务健康探测器"""
    def __init__(self):
        self.state = self._load_state()

    def _load_state(self):
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text())
            except:
                pass
        return {'services': {}, 'last_check': 0}

    def _save_state(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state, ensure_ascii=False, indent=1))

    def check_http(self, name, url, timeout=5):
        out, code = run_cmd(f"curl -sS -o /dev/null -w '%{{http_code}}' --max-time {timeout} {url}")
        status_code = out.replace("'", "").strip()
        healthy = code == 0 and status_code in ('200', '301', '302')
        self._update_state(name, 'http', healthy, {'url': url, 'status_code': status_code})
        return healthy

    def check_port(self, name, host, port):
        out, code = run_cmd(f"nc -z -w3 {host} {port}")
        healthy = code == 0
        self._update_state(name, 'port', healthy, {'host': host, 'port': port})
        return healthy

    def check_process(self, name, pattern):
        out, code = run_cmd(f"pgrep -f '{pattern}'")
        healthy = bool(out.strip())
        pids = out.strip().split('\n') if out.strip() else []
        self._update_state(name, 'process', healthy, {'pattern': pattern, 'pids': pids[:5]})
        return healthy

    def check_system_resource(self):
        issues = []
        out, _ = run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
        try:
            cpu = float(out)
            if cpu > 90:
                issues.append({'metric': 'cpu', 'value': cpu, 'threshold': 90})
        except:
            pass
        out, _ = run_cmd("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
        try:
            mem = float(out)
            if mem > 85:
                issues.append({'metric': 'memory', 'value': mem, 'threshold': 85})
        except:
            pass
        out, _ = run_cmd("df / | tail -1 | awk '{print $5}' | tr -d '%'")
        try:
            disk = int(out)
            if disk > 80:
                issues.append({'metric': 'disk', 'value': disk, 'threshold': 80})
        except:
            pass
        for issue in issues:
            bus.emit('resource_alert', issue, source='monitor')
        return issues

    def _update_state(self, name, check_type, healthy, details):
        prev = self.state.get('services', {}).get(name, {})
        was_healthy = prev.get('healthy', True)
        self.state.setdefault('services', {})[name] = {
            'healthy': healthy, 'check_type': check_type,
            'details': details, 'last_check': time.time(),
        }
        self._save_state()
        if was_healthy and not healthy:
            bus.emit('service_down', {'service': name, 'check_type': check_type, 'details': details, 'timestamp': datetime.now().isoformat()}, source='monitor')
        elif not was_healthy and healthy:
            bus.emit('service_recovered', {'service': name, 'check_type': check_type, 'timestamp': datetime.now().isoformat()}, source='monitor')

    def run_all_checks(self, rules=None):
        if rules is None:
            rules = self._default_rules()
        results = []
        for rule in rules:
            try:
                if rule['type'] == 'http':
                    ok = self.check_http(rule['name'], rule['url'])
                elif rule['type'] == 'port':
                    ok = self.check_port(rule['name'], rule['host'], rule['port'])
                elif rule['type'] == 'process':
                    ok = self.check_process(rule['name'], rule['pattern'])
                else:
                    continue
                results.append({'name': rule['name'], 'healthy': ok})
            except Exception as e:
                results.append({'name': rule['name'], 'healthy': False, 'error': str(e)})
        resource_issues = self.check_system_resource()
        if resource_issues:
            results.append({'name': 'system_resources', 'healthy': False, 'issues': resource_issues})
        self.state['last_check'] = time.time()
        self._save_state()
        return results

    def _default_rules(self):
        return [
            {'type': 'http', 'name': 'nginx', 'url': 'http://127.0.0.1'},
            {'type': 'port', 'name': 'mysql', 'host': '127.0.0.1', 'port': 3306},
            {'type': 'port', 'name': 'redis', 'host': '127.0.0.1', 'port': 6379},
            {'type': 'process', 'name': 'node_backend', 'pattern': 'node.*server'},
        ]

    def get_status(self):
        services = self.state.get('services', {})
        down = [k for k, v in services.items() if not v.get('healthy')]
        return {
            'total_services': len(services), 'healthy': len(services) - len(down),
            'down': down, 'last_check': datetime.fromtimestamp(self.state.get('last_check', 0)).isoformat() if self.state.get('last_check') else 'never',
            'details': services,
        }

monitor = ServiceMonitor()

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        print(json.dumps(monitor.get_status(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(monitor.run_all_checks(), ensure_ascii=False, indent=2))
