#!/usr/bin/env python3
"""
security.py — 安全执行层
白名单+危险命令拦截+审计日志
"""
import os
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

OPS_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
DATA_DIR = OPS_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

class SecureExecutor:
    SAFE_COMMANDS = [
        'systemctl restart', 'systemctl status', 'systemctl reload',
        'nginx -t', 'nginx -s reload',
        'pm2 restart', 'pm2 status',
        'df -h', 'free -m', 'ps aux', 'ss -tlnp',
        'certbot renew',
        'mysql -', 'mysqladmin',
        'curl -', 'find /data', 'find /var/log',
        'du -sh', 'ls -la', 'cat ', 'tail ', 'head ', 'grep ',
        'journalctl',
    ]

    DANGEROUS_PATTERNS = [
        'rm -rf /', 'rm -rf ~',
        'DROP TABLE', 'DROP DATABASE', 'DELETE FROM', 'TRUNCATE',
        'chmod 777', 'chmod -R 777',
        'iptables -F', 'ufw disable',
        'shutdown', 'reboot', 'halt', 'mkfs', 'fdisk',
    ]

    def __init__(self):
        self.audit_log = DATA_DIR / 'security_audit.jsonl'

    def is_dangerous(self, cmd):
        for p in self.DANGEROUS_PATTERNS:
            if p.lower() in cmd.lower():
                return True, p
        return False, None

    def is_safe(self, cmd):
        return any(cmd.startswith(s) for s in self.SAFE_COMMANDS)

    def execute(self, cmd, auto_mode=False, timeout=60):
        is_danger, dangerous = self.is_dangerous(cmd)
        if is_danger:
            self._audit('blocked', cmd, f'危险命令: {dangerous}')
            return {'status': 'blocked', 'reason': f'危险命令: {dangerous}'}

        if auto_mode and not self.is_safe(cmd):
            self._audit('blocked', cmd, '非白名单')
            return {'status': 'blocked', 'reason': '非白名单命令，需人工确认'}

        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                self._audit('failed', cmd, f'exit={result.returncode}')
                return {'status': 'failed', 'stderr': result.stderr[:500], 'exit_code': result.returncode}
            self._audit('success', cmd, result.stdout[:200])
            return {'status': 'success', 'stdout': result.stdout[:2000]}
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'reason': f'超时({timeout}s)'}
        except Exception as e:
            return {'status': 'error', 'reason': str(e)[:200]}

    def _audit(self, action, cmd, detail=''):
        entry = {'timestamp': datetime.now().isoformat(), 'action': action, 'command': cmd[:200], 'detail': detail[:200]}
        try:
            with open(DATA_DIR / 'security_audit.jsonl', 'a') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except:
            pass

secure_exec = SecureExecutor()
