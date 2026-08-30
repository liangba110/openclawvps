#!/usr/bin/env python3
"""
opsctl — 统一运维CLI工具（19条命令 + 自动扩展）
"""
import os, sys, json, subprocess, glob, time, re
from datetime import datetime, timedelta
from pathlib import Path

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except: return '', -1

# 安全：用 shlex.quote 防止密码特殊字符导致命令注入
import shlex
MYSQL_NM = "mysql -uroot -p" + shlex.quote(os.environ.get('MYSQL_PASSWORD', '')) + " -N huizhiyun"
LOG_MAP = {'ttdazi': '/opt/ttdazi/backend/app/ttdazi.log', 'pay': '/var/log/ttdazi_pay.log',
           'aiweb': '/var/log/aiweb.log', 'auth': '/var/log/auth.log', 'ops': '/opt/ttdazi/ops/logs'}

# ═══════════════════════════════════════════
# 核心命令
# ═══════════════════════════════════════════

def cmd_status():
    r = {'services': {}, 'system': {}}
    for n, u in [('ttdazi','http://127.0.0.1:5002/api/health'),('pay','http://127.0.0.1:5005/pay'),('aiweb','http://127.0.0.1:5003/api/health')]:
        o, _ = run(f"curl -sk -o /dev/null -w '%{{http_code}}' --max-time 3 {u}")
        r['services'][n] = {'http': int(o) if o.isdigit() else 0, 'ok': o == '200'}
    for s in ['mysql','caddy']:
        o, _ = run(f"systemctl is-active {s}")
        r['services'][s] = {'active': o == 'active', 'ok': o == 'active'}
    for p in ['/','/data/disk']:
        o, _ = run(f"df {p} | tail -1 | awk '{{print $3\"/\"$2\" \"$5}}'")
        r['system'][p] = o
    o, _ = run("cat /proc/loadavg | awk '{print $1, $2, $3}'")
    r['system']['load'] = o
    o, _ = run("free -h | grep Mem | awk '{print $3\"/\"$2}'")
    r['system']['memory'] = o
    r['summary'] = '✅ 全部正常' if all(s.get('ok',False) for s in r['services'].values()) else '⚠️ 部分异常'
    return {'status':'ok', **r}

def cmd_health():
    r = {'checks': [], 'alerts': []}
    for name, url in [('同途搭子','https://www.ttdazi.xyz/'),('AI建站','https://aiweb.openai2000.cn/'),('支付网关','https://pay.openai2000.cn/pay'),('官网','https://www.openai2000.cn/')]:
        o, _ = run(f"curl -sk -o /dev/null -w '%{{http_code}} %{{time_total}}' --max-time 10 -A 'Mozilla/5.0' {url}")
        p = o.split()
        code = int(p[0]) if p and p[0].isdigit() else 0
        ok = 200 <= code < 400 or code in (301,302)
        r['checks'].append({'name':name,'http_code':code,'ok':ok})
        if not ok: r['alerts'].append(f'{name}: HTTP {code}')
    for host in ['www.ttdazi.xyz','aiweb.openai2000.cn','pay.openai2000.cn','www.openai2000.cn']:
        o, _ = run(f"echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2")
        if o:
            try:
                from email.utils import parsedate_to_datetime
                exp = parsedate_to_datetime(o)
                days = (exp - datetime.now(exp.tzinfo)).days
                r['checks'].append({'name':f'SSL:{host}','days_left':days,'ok':days>14})
                if days <= 14: r['alerts'].append(f'{host} SSL将在{days}天后到期')
            except: pass
    for svc in ['mysql','caddy','ttdazi','ops-engine']:
        o, _ = run(f"systemctl is-active {svc}")
        r['checks'].append({'name':f'systemd:{svc}','active':o=='active','ok':o=='active'})
        if o != 'active': r['alerts'].append(f'{svc} 未运行')
    r['summary'] = {'total':len(r['checks']),'ok':sum(1 for c in r['checks'] if c.get('ok')),'alerts':len(r['alerts'])}
    return {'status':'ok', **r}

def cmd_deploy(args):
    project = args[0] if args else 'ttdazi'
    steps_map = {
        'ttdazi': [('build','cd /opt/ttdazi/frontend && npm run build 2>&1 | tail -3'),('deploy','bash /opt/ttdazi/deploy.sh 2>&1 | tail -5'),('verify','curl -sk -o /dev/null -w "%{http_code}" https://www.ttdazi.xyz/')],
        'ttdazi-backend': [('restart','sudo systemctl restart ttdazi'),('verify','curl -s http://127.0.0.1:5002/api/health')],
        'pay': [('restart','sudo systemctl restart ttdazi-pay'),('verify','curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5005/pay')],
        'aiweb': [('restart','sudo systemctl restart aiweb'),('verify','curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5003/api/health')],
    }
    if project not in steps_map:
        return {'status':'error','message':f'未知项目: {project}'}
    results = []
    for name, cmd in steps_map[project]:
        o, c = run(cmd, timeout=120)
        ok = c == 0 and ('200' in o or 'ok' in o.lower())
        results.append({'step':name,'ok':ok,'output':o[:200]})
    return {'status':'ok' if all(r['ok'] for r in results) else 'error','project':project,'steps':results}

def cmd_query(args):
    if '--user' in args:
        kw = args[args.index('--user')+1] if args.index('--user')+1 < len(args) else ''
        # SQL注入防护：只允许安全字符
        import re
        kw = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_\-\s]", "", kw)
        sql = f"SELECT id, nickname, phone, balance, created_at FROM user WHERE nickname LIKE '%{kw}%' OR phone LIKE '%{kw}%' LIMIT 20"
    elif '--order' in args:
        s = {'pending':'0','paid':'1','completed':'2'}.get(args[args.index('--order')+1],'0')
        sql = f"SELECT o.id, o.order_no, u.nickname, o.amount, o.status, o.created_at FROM orders o JOIN user u ON u.id=o.user_id WHERE o.status={s} ORDER BY o.id DESC LIMIT 20"
    elif '--money' in args:
        days = int(args[args.index('--money')+1]) if args.index('--money')+1 < len(args) and args[args.index('--money')+1].isdigit() else 7
        cutoff = (datetime.now()-timedelta(days=days)).strftime('%Y-%m-%d')
        sql = f"SELECT type, COUNT(*) as cnt, SUM(amount) as total FROM money_log WHERE created_at >= '{cutoff}' GROUP BY type ORDER BY total DESC"
    elif '--tables' in args:
        sql = "SELECT table_name, table_rows, ROUND(data_length/1024/1024,2) as MB FROM information_schema.tables WHERE table_schema='huizhiyun' ORDER BY data_length DESC"
    elif '--users-count' in args:
        sql = "SELECT COUNT(*) as total, SUM(CASE WHEN created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as '7天新增' FROM user"
    else:
        sql = ' '.join(args)
    if not sql: return {'status':'error','message':'用法: query <SQL> | --user/--order/--money/--tables/--users-count'}
    # SQL注入防护：禁止危险操作
    dangerous = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'UPDATE', 'INSERT', 'GRANT', 'REVOKE']
    sql_upper = sql.upper()
    for d in dangerous:
        if d in sql_upper:
            return {'status':'error','message':f'禁止执行: {d}操作'}
    o, c = run(f"{MYSQL_NM} -e \"{sql}\" 2>&1")
    return {'status':'ok' if c==0 else 'error','sql':sql[:200],'result':o[:2000]}

def cmd_logs(args):
    lines, grep, svc = 30, None, None
    i = 0
    while i < len(args):
        if args[i]=='--lines' and i+1<len(args): lines=int(args[i+1]); i+=2
        elif args[i]=='--grep' and i+1<len(args): grep=args[i+1]; i+=2
        elif args[i]=='errors': grep='ERROR|error|Traceback|Exception|FAIL|fatal'; i+=1
        else: svc=args[i]; i+=1
    if not svc: return {'status':'ok','available':list(LOG_MAP.keys())}
    path = LOG_MAP.get(svc,'')
    if not path: return {'status':'error','message':f'未知服务: {svc}'}
    if os.path.isdir(path):
        files = sorted(glob.glob(f'{path}/*.jsonl'), reverse=True)
        o, _ = run(f"tail -{lines} {files[0]}") if files else ('', 0)
    else:
        o, _ = run(f"grep -iE '{grep}' {path} | tail -{lines}" if grep else f"tail -{lines} {path}")
    return {'status':'ok','service':svc,'lines':len(o.split('\n')),'output':o[:3000]}

def cmd_backup(args):
    if args and args[0]=='clean':
        o, _ = run("ls -d /data/disk/daily_* 2>/dev/null | wc -l")
        c = int(o) if o.isdigit() else 0
        if c > 15: run(f"ls -d /data/disk/daily_* | head -{c-15} | xargs -r sudo rm -rf"); return {'status':'ok','message':f'清理{c-15}个'}
        return {'status':'ok','message':f'当前{c}个，无需清理'}
    o, _ = run("ls -d /data/disk/daily_* 2>/dev/null | wc -l")
    c = int(o) if o.isdigit() else 0
    o2, _ = run("ls -d /data/disk/daily_* 2>/dev/null | sort | tail -1")
    o3, _ = run("ls -d /data/disk/daily_* 2>/dev/null | sort | head -1")
    o4, _ = run(f"du -sh {o2}" if o2 else "echo ?")
    return {'status':'ok','count':c,'latest':os.path.basename(o2) if o2 else '无','oldest':os.path.basename(o3) if o3 else '无','size':o4.split()[0] if o4 else '?'}

def cmd_ssl():
    certs = []
    for host, srv in [('www.ttdazi.xyz','E'),('aiweb.openai2000.cn','A'),('pay.openai2000.cn','A'),('www.openai2000.cn','A')]:
        o, _ = run(f"echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null")
        days = -1
        if o:
            try:
                from email.utils import parsedate_to_datetime
                exp = parsedate_to_datetime(o.split('=',1)[1])
                days = (exp - datetime.now(exp.tzinfo)).days
            except: pass
        certs.append({'host':host,'server':srv,'days_left':days,'status':'ok' if days>14 else 'warning'})
    o, _ = run("systemctl is-enabled certbot.timer 2>/dev/null")
    return {'status':'ok','certs':certs,'certbot_auto_renew':o=='enabled'}

def cmd_git(args):
    if not args:
        o, _ = run("cd /opt/ttdazi && git status --short 2>/dev/null")
        return {'status':'ok','changes':o[:1000] or '无变更'}
    msg = ' '.join(args)
    r1, _ = run('cd /opt/ttdazi && git add -A')
    r2, c2 = run(f'cd /opt/ttdazi && git commit -m "{msg}" 2>&1')
    return {'status':'ok','message':msg,'committed':c2==0}

def cmd_search(args):
    if not args: return {'status':'error','message':'用法: search <pattern> [dir]'}
    p, d = args[0], args[1] if len(args)>1 else '/opt/ttdazi'
    o, _ = run(f"grep -rn '{p}' {d} --include='*.py' --include='*.js' --include='*.vue' --include='*.yaml' 2>/dev/null | head -30")
    return {'status':'ok','pattern':p,'matches':o[:3000] or '无匹配'}

def cmd_find(args):
    if not args: return {'status':'error','message':'用法: find <filename>'}
    o, _ = run(f"find /opt/ttdazi -name '*{args[0]}*' -type f 2>/dev/null | head -20")
    return {'status':'ok','found':o[:2000] or '未找到'}

def cmd_restart(args):
    if not args: return {'status':'error','message':'用法: restart <service>'}
    run(f"sudo systemctl restart {args[0]}", timeout=30)
    time.sleep(2)
    o, _ = run(f"systemctl is-active {args[0]}")
    return {'status':'ok','service':args[0],'active':o=='active'}

def cmd_port():
    o, _ = run("ss -tlnp | grep LISTEN")
    return {'status':'ok','listening':o[:2000]}

def cmd_top(n=10):
    o, _ = run(f"ps aux --sort=-%cpu | head -{n+1}")
    return {'status':'ok','processes':o[:2000]}

def cmd_disk():
    r = {'partitions':[],'large_dirs':[]}
    for line in run("df -h | grep -v tmpfs | tail -n +2")[0].split('\n'):
        p = line.split()
        if len(p)>=6: r['partitions'].append({'mount':p[5],'used':p[2],'size':p[1],'percent':p[4]})
    for line in run("du -sh /opt/ttdazi/* /opt/aiweb/* 2>/dev/null | sort -rh | head -10")[0].split('\n'):
        if '\t' in line: parts = line.split('\t',1); r['large_dirs'].append({'size':parts[0],'path':parts[1]})
    return {'status':'ok',**r}

def cmd_cron():
    o, _ = run("crontab -l 2>/dev/null")
    jobs = [l.strip() for l in o.split('\n') if l.strip() and not l.strip().startswith('#')]
    return {'status':'ok','count':len(jobs),'jobs':jobs}

def cmd_network():
    r = {'dns':{},'connectivity':{}}
    for d in ['www.ttdazi.xyz','aiweb.openai2000.cn','pay.openai2000.cn']:
        o, _ = run(f"dig +short {d} A 2>/dev/null | head -1")
        r['dns'][d] = o or '失败'
    for name, ip in [('腾讯云','223.5.5.5'),('Cloudflare','1.1.1.1')]:
        o, _ = run(f"ping -c 2 -W 3 {ip} 2>/dev/null | tail -1")
        r['connectivity'][name] = o.split('avg')[1].split('/')[1]+'ms' if 'avg' in o else '不可达'
    return {'status':'ok',**r}

def cmd_db(args):
    if not args:
        c, _ = run(f"{MYSQL_NM} -e \"SHOW STATUS LIKE 'Threads_connected';\" | awk '{{print $2}}'")
        q, _ = run(f"{MYSQL_NM} -e \"SHOW STATUS LIKE 'Queries';\" | awk '{{print $2}}'")
        t, _ = run(f"{MYSQL_NM} -e \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='huizhiyun';\"")
        return {'status':'ok','connections':c,'queries':q,'tables':t}
    if args[0]=='size':
        o, _ = run(f"{MYSQL_NM} -e \"SELECT table_name, table_rows, ROUND(data_length/1024/1024,2) as MB FROM information_schema.tables WHERE table_schema='huizhiyun' ORDER BY data_length DESC LIMIT 15;\"")
        return {'status':'ok','result':o[:2000]}
    if args[0]=='optimize':
        t = args[1] if len(args)>1 else 'money_log'
        o, _ = run(f"{MYSQL_NM} -e \"OPTIMIZE TABLE \\`{t}\\`;\"")
        return {'status':'ok','table':t,'result':o[:500]}
    return {'status':'error','message':'用法: db [size|optimize <table>]'}

def cmd_read(args):
    if not args: return {'status':'error','message':'用法: read <file> [lines]'}
    n = int(args[1]) if len(args)>1 and args[1].isdigit() else 30
    o, c = run(f"tail -{n} {args[0]}")
    return {'status':'ok' if c==0 else 'error','content':o[:5000]}

def cmd_service(args):
    if not args:
        svcs = ['ttdazi','ttdazi-pay','aiweb','mysql','caddy','ops-engine']
        return {'status':'ok','services':[{'name':s,'active':run(f"systemctl is-active {s}")[0]=='active'} for s in svcs]}
    if args[0] in ('start','stop','restart') and len(args)>1:
        run(f"sudo systemctl {args[0]} {args[1]}", timeout=30)
        time.sleep(2)
        o, _ = run(f"systemctl is-active {args[1]}")
        return {'status':'ok','service':args[1],'active':o=='active'}
    return {'status':'error','message':'用法: service [start|stop|restart] <服务名>'}

# ═══════════════════════════════════════════
# 自动生成的工具（由autopilot注入）
# ═══════════════════════════════════════════

def cmd_user_detail(args):
    """用户完整画像"""
    if not args: return {'status':'error','message':'用法: user-lookup <关键词>'}
    kw = args[0]
    o1, _ = run(f"{MYSQL_NM} -e \"SELECT id, nickname, phone, balance, created_at FROM user WHERE nickname LIKE '%{kw}%' OR phone LIKE '%{kw}%' LIMIT 5;\"")
    o2, _ = run(f"{MYSQL_NM} -e \"SELECT o.id, o.amount, o.status, o.created_at FROM orders o JOIN user u ON u.id=o.user_id WHERE u.nickname LIKE '%{kw}%' ORDER BY o.id DESC LIMIT 10;\"")
    o3, _ = run(f"{MYSQL_NM} -e \"SELECT c.id, c.is_online, c.expires_at FROM companion c JOIN user u ON u.id=c.user_id WHERE u.nickname LIKE '%{kw}%';\"")
    return {'status':'ok','user':o1,'orders':o2,'companions':o3}

def cmd_error_hunt(args):
    """扫描所有日志找错误"""
    errors = []
    for name, path in LOG_MAP.items():
        if name == 'ops' or not os.path.exists(path): continue
        o, _ = run(f"grep -iE 'ERROR|Exception|Traceback|FATAL' {path} | tail -5")
        for line in o.split('\n'):
            if line.strip(): errors.append({'source':name,'error':line.strip()[:200]})
    return {'status':'ok','error_count':len(errors),'errors':errors[:20]}

def cmd_db_health(args):
    """数据库深度健康"""
    checks = {}
    for metric, sql in [('connections',"SHOW STATUS LIKE 'Threads_connected'"),('queries',"SHOW STATUS LIKE 'Queries'"),('slow',"SHOW STATUS LIKE 'Slow_queries'"),('running',"SHOW STATUS LIKE 'Threads_running'")]:
        o, _ = run(f"{MYSQL_NM} -e \"{sql}\" | awk '{{print $2}}'")
        checks[metric] = o
    o, _ = run(f"{MYSQL_NM} -e \"SELECT table_name, ROUND(DATA_FREE/(DATA_LENGTH+1)*100,1) as frag FROM information_schema.tables WHERE table_schema='huizhiyun' AND DATA_FREE>0 ORDER BY frag DESC LIMIT 5;\"")
    checks['fragmented'] = o
    return {'status':'ok','db_health':checks}

# ═══════════════════════════════════════════
# CLI入口
# ═══════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("opsctl — 统一运维CLI（19条命令）")
        print("用法: opsctl <command> [args]")
        print("命令: status health deploy query logs backup ssl git search find restart port top disk cron network db read service user-lookup error-hunter db-health")
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    handlers = {
        'status': lambda: cmd_status(), 'health': lambda: cmd_health(),
        'deploy': lambda: cmd_deploy(args), 'query': lambda: cmd_query(args),
        'logs': lambda: cmd_logs(args), 'backup': lambda: cmd_backup(args),
        'ssl': lambda: cmd_ssl(), 'git': lambda: cmd_git(args),
        'search': lambda: cmd_search(args), 'find': lambda: cmd_find(args),
        'restart': lambda: cmd_restart(args), 'port': lambda: cmd_port(),
        'top': lambda: cmd_top(int(args[0]) if args else 10),
        'disk': lambda: cmd_disk(), 'cron': lambda: cmd_cron(),
        'network': lambda: cmd_network(), 'db': lambda: cmd_db(args),
        'read': lambda: cmd_read(args), 'service': lambda: cmd_service(args),
        'user-lookup': lambda: cmd_user_detail(args),
        'error-hunter': lambda: cmd_error_hunt(args),
        'db-health': lambda: cmd_db_health(args),
    }

    handler = handlers.get(cmd)
    if not handler:
        print(json.dumps({'status':'error','message':f'未知命令: {cmd}，可用: {", ".join(handlers.keys())}'}, ensure_ascii=False))
        return

    result = handler()
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 记录操作（供autopilot分析）
    try:
        sys.path.insert(0, os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
        from autopilot import log_operation
        log_operation(cmd, args, result.get('status', 'ok'))
    except: pass

if __name__ == '__main__':
    main()
