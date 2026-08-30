#!/usr/bin/env python3
"""
ops-autopilot — 自动开发引擎
Hermes调用此工具，自动分析操作模式 → 生成新Python工具 → 扩展opsctl

用法:
  python3 /opt/ttdazi/ops/autopilot.py --scan          # 扫描操作日志，发现高频模式
  python3 /opt/ttdazi/ops/autopilot.py --suggest        # 生成新工具建议
  python3 /opt/ttdazi/ops/autopilot.py --generate <id>  # 自动生成工具代码
  python3 /opt/ttdazi/ops/autopilot.py --install <file>  # 安装新工具到opsctl
  python3 /opt/ttdazi/ops/autopilot.py --report         # 综合报告

原理:
  1. 记录每次opsctl调用 + Hermes会话中的操作
  2. 统计高频模式（哪些操作组合经常一起出现）
  3. 自动生成可复用的Python函数
  4. 注册到opsctl，下次一条命令完成
"""
import os
import sys
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
LOG_DIR = BASE_DIR / 'logs'
PATTERNS_FILE = BASE_DIR / 'data' / 'operation_patterns.json'
TOOLS_DIR = BASE_DIR / 'auto_tools'
TOOLS_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / 'data').mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════
# 1. 操作记录器（被opsctl调用）
# ═══════════════════════════════════════════

def log_operation(command, args, result_status, duration_ms=0):
    """记录一次操作（由opsctl调用）"""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'command': command,
        'args': args,
        'status': result_status,
        'duration_ms': duration_ms
    }

    log_file = LOG_DIR / f"ops_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    with open(log_file, 'a') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

# ═══════════════════════════════════════════
# 2. 模式扫描器
# ═══════════════════════════════════════════

def scan_patterns(days=7):
    """扫描操作日志，发现高频模式"""
    commands = Counter()
    sequences = Counter()  # 命令序列（连续操作）
    arg_patterns = defaultdict(Counter)  # 参数模式
    hourly = defaultdict(Counter)  # 按小时分布

    cutoff = datetime.now() - timedelta(days=days)

    for log_file in sorted(LOG_DIR.glob('ops_*.jsonl')):
        try:
            date_str = log_file.stem.replace('ops_', '')
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            if file_date < cutoff:
                continue
        except:
            continue

        prev_cmd = None
        for line in log_file.read_text().strip().split('\n'):
            if not line:
                continue
            try:
                entry = json.loads(line)
            except:
                continue

            cmd = entry.get('command', '')
            args = entry.get('args', [])
            ts = entry.get('timestamp', '')

            # 统计命令频率
            commands[cmd] += 1

            # 统计命令序列（A→B连续出现）
            if prev_cmd and prev_cmd != cmd:
                seq = f"{prev_cmd}→{cmd}"
                sequences[seq] += 1
            prev_cmd = cmd

            # 统计参数模式
            if args:
                arg_patterns[cmd][str(args[:2])] += 1

            # 按小时分布
            try:
                hour = datetime.fromisoformat(ts).hour
                hourly[cmd][hour] += 1
            except:
                pass

    return {
        'command_frequency': dict(commands.most_common(20)),
        'sequences': dict(sequences.most_common(10)),
        'arg_patterns': {k: dict(v.most_common(5)) for k, v in arg_patterns.items()},
        'hourly_patterns': {k: dict(v) for k, v in hourly.items()},
        'total_operations': sum(commands.values()),
        'scan_period_days': days
    }

# ═══════════════════════════════════════════
# 3. 工具建议生成器
# ═══════════════════════════════════════════

# 已有opsctl命令（排除）
EXISTING_COMMANDS = {
    'status', 'health', 'deploy', 'query', 'logs', 'backup', 'ssl',
    'git', 'search', 'find', 'restart', 'port', 'top', 'disk', 'cron',
    'network', 'db', 'read', 'service'
}

# 高频操作模板
TOOL_TEMPLATES = {
    'user_lookup': {
        'name': '用户详情查询',
        'description': '一条命令查用户完整信息（基本信息+订单+余额+搭子）',
        'trigger': 'query --user 高频',
        'pattern': 'query.*--user',
        'code': '''
def cmd_user_detail(args):
    """用户完整画像"""
    if not args:
        return fail('用法: opsctl user <关键词>')
    kw = args[0]
    MYSQL = f"mysql -uroot -p'{os.environ.get("MYSQL_PASSWORD", "")}' -N {os.environ.get("MYSQL_DB", "huizhiyun")}"

    # 基本信息
    out, _ = run(f"{MYSQL} -e \\"SELECT id, nickname, phone, balance, created_at FROM user WHERE nickname LIKE '%{kw}%' OR phone LIKE '%{kw}%' LIMIT 5;\\"")

    # 该用户的订单
    out2, _ = run(f"{MYSQL} -e \\"SELECT o.id, o.amount, o.status, o.created_at FROM orders o JOIN user u ON u.id=o.user_id WHERE u.nickname LIKE '%{kw}%' ORDER BY o.id DESC LIMIT 10;\\"")

    # 该用户的搭子
    out3, _ = run(f"{MYSQL} -e \\"SELECT c.id, c.is_online, c.expires_at FROM companion c JOIN user u ON u.id=c.user_id WHERE u.nickname LIKE '%{kw}%';\\"")

    return {'status': 'ok', 'user': out, 'orders': out2, 'companions': out3}
''',
    },
    'quick_deploy': {
        'name': '快速部署（自动判断项目）',
        'description': '自动检测改动了哪个项目并部署',
        'trigger': 'deploy 高频',
        'pattern': 'deploy',
        'code': '''
def cmd_quick_deploy(args):
    """智能部署：自动检测改动"""
    # 检查git状态
    out, _ = run("cd /opt/ttdazi && git status --short 2>/dev/null")
    changed_files = out.strip().split('\\n') if out else []

    # 判断项目
    project = 'ttdazi'
    for f in changed_files:
        if 'payment' in f or 'pay' in f:
            project = 'pay'
        elif 'aiweb' in f:
            project = 'aiweb'
        elif 'frontend' in f:
            project = 'ttdazi'

    return cmd_deploy(project)
''',
    },
    'backup_report': {
        'name': '备份报告',
        'description': '备份状态+大小+完整性+建议',
        'trigger': 'backup 高频',
        'pattern': 'backup',
        'code': '''
def cmd_backup_report(args):
    """详细备份报告"""
    result = cmd_backup(args)

    # 检查最新备份完整性
    out, _ = run("ls -d /data/disk/daily_* 2>/dev/null | sort | tail -1")
    if out:
        latest = out
        # 检查是否包含关键文件
        tables_ok, _ = run(f"tar tzf {latest}/databases.tar.gz 2>/dev/null | grep -c '.sql'")
        src_ok, _ = run(f"tar tzf {latest}/source_code.tar.gz 2>/dev/null | wc -l")

        result['integrity'] = {
            'tables': int(tables_ok) if tables_ok.isdigit() else 0,
            'source_files': int(src_ok) if src_ok.isdigit() else 0
        }

    return result
''',
    },
    'service_health': {
        'name': '服务健康看板',
        'description': '所有服务+进程+端口+资源一目了然',
        'trigger': 'status + health 组合高频',
        'pattern': 'status.*health|health.*status',
        'code': '''
def cmd_dashboard(args):
    """综合健康看板"""
    result = {}

    # 服务状态
    services = ['ttdazi', 'ttdazi-pay', 'aiweb', 'mysql', 'caddy', 'ops-engine']
    for svc in services:
        out, _ = run(f"systemctl is-active {svc}")
        pid, _ = run(f"systemctl show {svc} --property=MainPID --value")
        mem, _ = run(f"ps -o rss= -p {pid.strip()} 2>/dev/null")
        result[svc] = {
            'active': out == 'active',
            'pid': pid.strip(),
            'memory_mb': round(int(mem.strip()) / 1024, 1) if mem.strip().isdigit() else 0
        }

    # 端口
    out, _ = run("ss -tlnp | grep LISTEN | awk '{print $4}' | sed 's/.*://' | sort -n | uniq")
    result['ports'] = [int(p) for p in out.split() if p.isdigit()]

    return {'status': 'ok', 'dashboard': result}
''',
    },
    'error_hunter': {
        'name': '错误猎手',
        'description': '扫描所有日志找最近错误，按严重度排序',
        'trigger': 'logs errors 高频',
        'pattern': 'logs.*errors',
        'code': '''
def cmd_error_hunt(args):
    """扫描所有日志找错误"""
    log_files = {
        'ttdazi': '/opt/ttdazi/backend/app/ttdazi.log',
        'pay': '/var/log/ttdazi_pay.log',
        'aiweb': '/var/log/aiweb.log',
        'auth': '/var/log/auth.log',
    }
    errors = []
    for name, path in log_files.items():
        if not os.path.exists(path):
            continue
        out, _ = run(f"grep -iE 'ERROR|Exception|Traceback|FATAL|critical' {path} | tail -5")
        for line in out.split('\\n'):
            if line.strip():
                errors.append({'source': name, 'error': line.strip()[:200]})

    errors.sort(key=lambda x: x['source'])
    return {'status': 'ok', 'error_count': len(errors), 'errors': errors[:20]}
''',
    },
    'domain_check': {
        'name': '域名全面检查',
        'description': 'DNS解析+HTTP状态+SSL证书+响应时间',
        'trigger': 'ssl + health 组合高频',
        'pattern': 'ssl.*health|health.*ssl',
        'code': '''
def cmd_domain_check(args):
    """域名全面检查"""
    domains = ['www.ttdazi.xyz', 'aiweb.openai2000.cn', 'pay.openai2000.cn', 'www.openai2000.cn']
    results = []
    for domain in domains:
        # DNS
        dns, _ = run(f"dig +short {domain} A | head -1")
        # HTTP
        http, _ = run(f"curl -sk -o /dev/null -w '%{{http_code}} %{{time_total}}' --max-time 5 -A 'Mozilla/5.0' https://{domain}/")
        parts = http.split()
        code = parts[0] if parts else '0'
        time_s = parts[1] if len(parts) > 1 else '0'
        # SSL
        ssl_out, _ = run(f"echo | openssl s_client -connect {domain}:443 -servername {domain} 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2")
        days = -1
        if ssl_out:
            try:
                from email.utils import parsedate_to_datetime
                exp = parsedate_to_datetime(ssl_out)
                days = (exp - datetime.now(exp.tzinfo)).days
            except: pass

        results.append({
            'domain': domain, 'dns': dns, 'http_code': code,
            'response_ms': round(float(time_s) * 1000) if time_s else 0,
            'ssl_days': days
        })
    return {'status': 'ok', 'domains': results}
''',
    },
    'db_health': {
        'name': '数据库深度健康',
        'description': '连接数+查询数+表大小+碎片+慢查询+锁',
        'trigger': 'db 高频',
        'pattern': 'db|query.*--tables',
        'code': '''
def cmd_db_health(args):
    """数据库深度健康报告"""
    MYSQL = f"mysql -uroot -p'{os.environ.get("MYSQL_PASSWORD", "")}' -N {os.environ.get("MYSQL_DB", "huizhiyun")}"

    checks = {}
    for metric, sql in [
        ('connections', "SHOW STATUS LIKE 'Threads_connected'"),
        ('max_connections', "SHOW VARIABLES LIKE 'max_connections'"),
        ('queries', "SHOW STATUS LIKE 'Queries'"),
        ('slow_queries', "SHOW STATUS LIKE 'Slow_queries'"),
        ('threads_running', "SHOW STATUS LIKE 'Threads_running'"),
    ]:
        out, _ = run(f"{MYSQL} -e \\"{sql}\\" | awk '{{print $2}}'")
        checks[metric] = out

    # 表碎片
    out, _ = run(f"{MYSQL} -e \\"SELECT table_name, ROUND(DATA_FREE/(DATA_LENGTH+1)*100,1) as frag FROM information_schema.tables WHERE table_schema='huizhiyun' AND DATA_FREE > 0 ORDER BY frag DESC LIMIT 5;\\"")
    checks['fragmented_tables'] = out

    return {'status': 'ok', 'db_health': checks}
''',
    },
}

def suggest_tools(patterns):
    """基于扫描结果生成工具建议"""
    suggestions = []

    for tool_id, template in TOOL_TEMPLATES.items():
        # 检查是否已安装
        if (TOOLS_DIR / f'{tool_id}.py').exists():
            continue

        # 检查触发条件
        freq = patterns.get('command_frequency', {})
        sequences = patterns.get('sequences', {})

        score = 0
        reason = []

        if 'query' in freq and freq['query'] >= 3:
            if tool_id == 'user_lookup':
                score += freq['query']
                reason.append(f"query命令使用{freq['query']}次")

        if 'deploy' in freq and freq['deploy'] >= 2:
            if tool_id == 'quick_deploy':
                score += freq['deploy']
                reason.append(f"deploy命令使用{freq['deploy']}次")

        if 'backup' in freq and freq['backup'] >= 2:
            if tool_id == 'backup_report':
                score += freq['backup']
                reason.append(f"backup命令使用{freq['backup']}次")

        if 'status' in freq and 'health' in freq:
            if tool_id == 'service_health':
                score += freq.get('status', 0) + freq.get('health', 0)
                reason.append(f"status+health组合高频")

        if 'logs' in freq and freq['logs'] >= 2:
            if tool_id == 'error_hunter':
                score += freq['logs']
                reason.append(f"logs命令使用{freq['logs']}次")

        if 'db' in freq and freq['db'] >= 2:
            if tool_id == 'db_health':
                score += freq['db']
                reason.append(f"db命令使用{freq['db']}次")

        if score > 0:
            suggestions.append({
                'id': tool_id,
                'name': template['name'],
                'description': template['description'],
                'score': score,
                'reason': reason,
            })

    suggestions.sort(key=lambda x: x['score'], reverse=True)
    return suggestions

# ═══════════════════════════════════════════
# 4. 工具代码生成器
# ═══════════════════════════════════════════

def generate_tool(tool_id):
    """自动生成工具代码"""
    if tool_id not in TOOL_TEMPLATES:
        return None

    template = TOOL_TEMPLATES[tool_id]
    code = f'''#!/usr/bin/env python3
"""
{template['name']} — 自动生成于{datetime.now().strftime('%Y-%m-%d %H:%M')}
{template['description']}
"""
import os, sys, json, subprocess
from datetime import datetime

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except: return '', -1

def ok(msg): return {{'status': 'ok', 'message': msg}}
def fail(msg): return {{'status': 'error', 'message': msg}}

# ── 核心逻辑 ──
{template['code']}

# ── CLI入口 ──
if __name__ == '__main__':
    args = sys.argv[1:]
    # 查找cmd_开头的函数
    func_name = 'cmd_{tool_id.replace("_", "_")}'
    # 动态调用
    for name, obj in list(globals().items()):
        if name.startswith('cmd_') and callable(obj):
            result = obj(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            break
'''
    tool_path = TOOLS_DIR / f'{tool_id}.py'
    tool_path.write_text(code)
    return str(tool_path)

# ═══════════════════════════════════════════
# 5. 安装器（注册到opsctl）
# ═══════════════════════════════════════════

tool_cmd_name = ""
def ok(msg): return {"status": "ok", "message": msg}
def fail(msg): return {"status": "error", "message": msg}
def install_tool(tool_id):
    """安装自动生成的工具到opsctl"""
    tool_file = TOOLS_DIR / f'{tool_id}.py'
    if not tool_file.exists():
        # 自动生成
        generate_tool(tool_id)

    if not tool_file.exists():
        return fail(f'工具 {tool_id} 不存在')

    # 注册到opsctl的handlers
    opsctl_path = BASE_DIR / 'opsctl.py'
    content = opsctl_path.read_text()

    # 检查是否已注册
    if f"'{tool_id}'" in content:
        return ok(f'{tool_id} 已注册')

    # 导入工具代码
    tool_code = tool_file.read_text()

    # 提取函数定义
    func_match = re.search(r'(def cmd_\w+\(args\):.*?)(?=\n# ──|\nif __name__)', tool_code, re.DOTALL)
    if not func_match:
        return fail(f'无法从 {tool_id}.py 提取函数')

    func_code = func_match.group(1).strip()

    # 找到CLI路由中的handlers字典，在其前面插入函数定义
    insert_point = content.find('# ═══ CLI路由')
    if insert_point == -1:
        insert_point = content.find('def main():')

    # 插入函数
    new_content = content[:insert_point] + func_code + '\n\n' + content[insert_point:]

    # 注册到handlers
    tool_cmd_name = tool_id.replace('_', '-')
    new_content = new_content.replace(
        "    handlers = {",
        f"    handlers = {{\n        '{tool_cmd_name}': lambda: cmd_{tool_id}(args),"
    )

    opsctl_path.write_text(new_content)
    return ok(f'✅ {tool_id} 已安装到opsctl，命令: opsctl {tool_cmd_name}')

# ═══════════════════════════════════════════
# 6. 综合报告
# ═══════════════════════════════════════════

def generate_report():
    """生成综合报告"""
    print("🤖 Ops Autopilot — 自动开发报告")
    print("=" * 50)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 扫描模式
    patterns = scan_patterns()
    print(f"\n📊 操作统计 (近7天): {patterns['total_operations']}次操作")

    if patterns['command_frequency']:
        print("\n📈 命令频率:")
        for cmd, count in list(patterns['command_frequency'].items())[:8]:
            print(f"  {cmd}: {count}次")

    if patterns['sequences']:
        print("\n🔗 操作序列:")
        for seq, count in list(patterns['sequences'].items())[:5]:
            print(f"  {seq}: {count}次")

    # 工具建议
    suggestions = suggest_tools(patterns)
    if suggestions:
        print(f"\n💡 建议生成的工具 ({len(suggestions)}个):")
        for s in suggestions:
            print(f"  🔧 {s['name']}")
            print(f"    原因: {', '.join(s['reason'])}")
            print(f"    描述: {s['description']}")
    else:
        print("\n✅ 暂无新工具建议（操作频率不足或工具已存在）")

    # 已安装的自动生成工具
    installed = list(TOOLS_DIR.glob('*.py'))
    if installed:
        print(f"\n📦 已安装的自动生成工具 ({len(installed)}个):")
        for t in installed:
            print(f"  {t.stem}")

    print("\n" + "=" * 50)

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == '--scan':
        patterns = scan_patterns()
        print(json.dumps(patterns, ensure_ascii=False, indent=2))
    elif cmd == '--suggest':
        patterns = scan_patterns()
        suggestions = suggest_tools(patterns)
        print(json.dumps(suggestions, ensure_ascii=False, indent=2))
    elif cmd == '--generate' and len(sys.argv) > 2:
        tool_id = sys.argv[2]
        result = generate_tool(tool_id)
        if result:
            print(f'✅ 生成: {result}')
        else:
            print(f'❌ 未知工具: {tool_id}')
    elif cmd == '--install' and len(sys.argv) > 2:
        tool_id = sys.argv[2]
        result = install_tool(tool_id)
        print(json.dumps(result, ensure_ascii=False))
    elif cmd == '--report':
        generate_report()
    else:
        print('用法: --scan | --suggest | --generate <id> | --install <id> | --report')
