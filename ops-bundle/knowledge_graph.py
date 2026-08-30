#!/usr/bin/env python3
"""
knowledge_graph.py — 服务依赖知识图谱
功能：
  - 自动发现服务依赖关系
  - 故障影响分析（A挂了影响哪些下游？）
  - 根因推导（哪个上游导致的故障？）
  - 拓扑可视化

用法:
  python3 knowledge_graph.py discover     # 自动发现依赖
  python3 knowledge_graph.py impact mysql  # 分析mysql故障影响
  python3 knowledge_graph.py root nginx_502 # 根因推导
  python3 knowledge_graph.py show          # 显示拓扑
"""
import os
import sys
import json
import subprocess
import sqlite3
import time
from pathlib import Path
from collections import defaultdict

OPS_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
DATA_DIR = OPS_DIR / 'data'
KG_DB = DATA_DIR / 'knowledge_graph.db'
DATA_DIR.mkdir(parents=True, exist_ok=True)

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ''

# ═══════════════════════════════════════════
# 知识图谱数据库
# ═══════════════════════════════════════════

class KnowledgeGraph:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = str(KG_DB)
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        self.db.execute('''CREATE TABLE IF NOT EXISTS services (
            name TEXT PRIMARY KEY,
            type TEXT,
            host TEXT,
            port INTEGER,
            status TEXT DEFAULT 'unknown',
            last_check REAL,
            metadata TEXT
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS dependencies (
            source TEXT,
            target TEXT,
            dep_type TEXT,
            description TEXT,
            critical INTEGER DEFAULT 1,
            PRIMARY KEY (source, target)
        )''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS fault_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL,
            service TEXT,
            fault_type TEXT,
            impact TEXT,
            root_cause TEXT,
            resolution TEXT,
            duration_sec INTEGER
        )''')
        self.db.commit()

    # ── 服务注册 ──
    def add_service(self, name, stype, host='127.0.0.1', port=None, metadata=None):
        self.db.execute(
            'INSERT OR REPLACE INTO services(name, type, host, port, metadata) VALUES(?,?,?,?,?)',
            (name, stype, host, port, json.dumps(metadata or {}))
        )
        self.db.commit()

    def add_dependency(self, source, target, dep_type='depends_on', description='', critical=True):
        self.db.execute(
            'INSERT OR REPLACE INTO dependencies(source, target, dep_type, description, critical) VALUES(?,?,?,?,?)',
            (source, target, dep_type, description, int(critical))
        )
        self.db.commit()

    def update_status(self, name, status):
        self.db.execute(
            'UPDATE services SET status=?, last_check=? WHERE name=?',
            (status, time.time(), name)
        )
        self.db.commit()

    # ── 影响分析 ──
    def get_impact(self, service, visited=None):
        """分析某服务故障的影响范围（BFS下游）"""
        if visited is None:
            visited = set()
        if service in visited:
            return []
        visited.add(service)

        impacts = []
        cur = self.db.execute(
            'SELECT source, description, critical FROM dependencies WHERE target=?',
            (service,)
        )
        for row in cur.fetchall():
            dependent, desc, critical = row
            impacts.append({
                'service': dependent,
                'via': service,
                'description': desc,
                'critical': bool(critical),
            })
            # 递归查找下游影响
            sub = self.get_impact(dependent, visited)
            impacts.extend(sub)

        return impacts

    # ── 根因推导 ──
    def find_root_cause(self, symptom_service, visited=None):
        """从症状往上追溯根因（BFS上游）"""
        if visited is None:
            visited = set()
        if symptom_service in visited:
            return []
        visited.add(symptom_service)

        causes = []
        cur = self.db.execute(
            'SELECT target, description, critical FROM dependencies WHERE source=?',
            (symptom_service,)
        )
        for row in cur.fetchall():
            dependency, desc, critical = row
            # 检查该依赖是否健康
            svc = self.db.execute('SELECT status FROM services WHERE name=?', (dependency,)).fetchone()
            status = svc[0] if svc else 'unknown'

            causes.append({
                'service': dependency,
                'status': status,
                'relation': desc,
                'critical': bool(critical),
                'likely_root': status not in ('healthy', 'unknown'),
            })

            if status not in ('healthy', 'unknown'):
                sub = self.find_root_cause(dependency, visited)
                causes.extend(sub)

        return causes

    # ── 自动发现 ──
    def auto_discover(self):
        """自动发现服务依赖关系"""
        # 清空旧数据重新发现
        self.db.execute('DELETE FROM services')
        self.db.execute('DELETE FROM dependencies')

        # 1. 发现Nginx
        nginx_upstream = run_cmd("grep -r 'proxy_pass\\|upstream' /etc/nginx/sites-enabled/ 2>/dev/null | grep -oP 'http://\\K[^:/\\s]+|upstream \\K[^\\s{]+'")
        self.add_service('nginx', 'web_server', port=80)
        for upstream in set(nginx_upstream.split('\n')):
            if upstream and upstream not in ('127.0.0.1', 'localhost', ''):
                self.add_dependency('nginx', upstream, 'reverse_proxy', f'Nginx反向代理到{upstream}')

        # 2. 发现Node后端
        node_ports = run_cmd("ss -tlnp | grep node | awk '{print $4}' | grep -oP ':\\K[0-9]+'")
        for port in set(node_ports.split('\n')):
            if port:
                name = f'node_{port}'
                self.add_service(name, 'node_app', port=int(port))
                self.add_dependency('nginx', name, 'reverse_proxy', f'Nginx代理:{port}')

        # 3. 发现MySQL
        self.add_service('mysql', 'database', port=3306)
        # 找哪些应用连MySQL
        for svc in self.db.execute('SELECT name FROM services WHERE type != "database"').fetchall():
            self.add_dependency(svc[0], 'mysql', 'database', f'{svc[0]}依赖MySQL')

        # 4. 发现Redis
        redis_used = run_cmd("grep -rl 'redis\\|REDIS' /opt/ttdazi/ /data/web/ 2>/dev/null | head -5")
        if redis_used:
            self.add_service('redis', 'cache', port=6379)
            for svc in self.db.execute('SELECT name FROM services WHERE type = "node_app"').fetchall():
                self.add_dependency(svc[0], 'redis', 'cache', f'{svc[0]}使用Redis缓存')

        # 5. 发现SSL证书依赖
        domains = run_cmd("ls /etc/letsencrypt/live/ 2>/dev/null").split('\n')
        for domain in domains:
            if domain and domain not in ('README', ''):
                self.add_service(f'ssl:{domain}', 'ssl_cert')
                self.add_dependency('nginx', f'ssl:{domain}', 'ssl', f'Nginx使用{domain}证书')

        # 6. 更新当前状态
        self._check_all_status()

        return self.get_topology()

    def _check_all_status(self):
        """检查所有服务状态"""
        for svc in self.db.execute('SELECT name, type, host, port FROM services').fetchall():
            name, stype, host, port = svc
            if stype in ('web_server', 'node_app', 'database', 'cache') and port:
                out = run_cmd(f"nc -z -w2 {host} {port} && echo ok || echo fail")
                self.update_status(name, 'healthy' if 'ok' in out else 'down')
            elif stype == 'ssl_cert':
                domain = name.replace('ssl:', '')
                out = run_cmd(f"echo | openssl s_client -connect {domain}:443 -servername {domain} 2>/dev/null | openssl x509 -noout -checkend 604800 && echo ok || echo expiring")
                self.update_status(name, 'healthy' if 'ok' in out else 'expiring')

    def get_topology(self):
        """返回完整拓扑"""
        services = {}
        for row in self.db.execute('SELECT name, type, host, port, status, metadata FROM services').fetchall():
            services[row[0]] = {
                'type': row[1], 'host': row[2], 'port': row[3],
                'status': row[4], 'metadata': json.loads(row[5] or '{}')
            }

        deps = []
        for row in self.db.execute('SELECT source, target, dep_type, description, critical FROM dependencies').fetchall():
            deps.append({
                'source': row[0], 'target': row[1], 'type': row[2],
                'description': row[3], 'critical': bool(row[4])
            })

        return {'services': services, 'dependencies': deps}

    def show_topology(self):
        """文本可视化拓扑"""
        topo = self.get_topology()
        lines = ['═══ 服务依赖拓扑 ═══\n']

        # 按层级排列
        layers = defaultdict(list)
        for name, svc in topo['services'].items():
            layers[svc['type']].append((name, svc))

        type_icons = {
            'web_server': '🌐', 'node_app': '⚡', 'database': '🗄️',
            'cache': '💾', 'ssl_cert': '🔒', 'unknown': '❓'
        }

        for layer_type in ['web_server', 'node_app', 'database', 'cache', 'ssl_cert']:
            if layer_type in layers:
                for name, svc in layers[layer_type]:
                    icon = type_icons.get(svc['type'], '❓')
                    status_icon = '✅' if svc['status'] == 'healthy' else ('❌' if svc['status'] == 'down' else '⚠️')
                    lines.append(f"  {icon} {status_icon} {name} ({svc['status']})")

        lines.append('\n═══ 依赖关系 ═══\n')
        for dep in topo['dependencies']:
            critical = '🔴' if dep['critical'] else '🟡'
            lines.append(f"  {dep['source']} ──{critical}→ {dep['target']}  ({dep['description']})")

        return '\n'.join(lines)

# CLI
if __name__ == '__main__':
    kg = KnowledgeGraph()
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'

    if cmd == 'discover':
        topo = kg.auto_discover()
        print(json.dumps(topo, ensure_ascii=False, indent=2))
    elif cmd == 'impact' and len(sys.argv) > 2:
        impacts = kg.get_impact(sys.argv[2])
        print(f"\n═══ {sys.argv[2]} 故障影响分析 ═══\n")
        if impacts:
            for imp in impacts:
                critical = '🔴' if imp['critical'] else '🟡'
                print(f"  {critical} {imp['service']}（通过 {imp['via']}）: {imp['description']}")
        else:
            print("  无下游影响")
    elif cmd == 'root' and len(sys.argv) > 2:
        causes = kg.find_root_cause(sys.argv[2])
        print(f"\n═══ {sys.argv[2]} 根因推导 ═══\n")
        if causes:
            for cause in causes:
                likely = '🎯' if cause['likely_root'] else '  '
                print(f"  {likely} {cause['service']} [{cause['status']}] — {cause['relation']}")
        else:
            print("  未发现上游异常")
    elif cmd == 'show':
        print(kg.show_topology())
    else:
        print('用法: discover | impact <service> | root <symptom> | show')
