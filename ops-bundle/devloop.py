#!/usr/bin/env python3
"""
devloop.py — 开发闭环：检测→工单→Hermes处理→修复→部署
当运维自动化解决不了的问题（代码bug/配置错误/逻辑问题），自动升级给Hermes

用法:
  python3 /opt/ttdazi/ops/devloop.py ticket "错误描述"  # 创建工单
  python3 /opt/ttdazi/ops/devloop.py status             # 查看工单队列
  python3 /opt/ttdazi/ops/devloop.py done <id>          # 标记完成
  python3 /opt/ttdazi/ops/devloop.py context <id>       # 获取工单完整上下文
"""
import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
TICKETS_DIR = BASE_DIR / 'data' / 'tickets'
TICKETS_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════
# 工单系统
# ═══════════════════════════════════════════

def create_ticket(error_description, source='engine', severity='warn'):
    """创建开发工单"""
    ticket_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 收集上下文
    context = collect_dev_context(error_description)
    
    ticket = {
        'id': ticket_id,
        'status': 'open',
        'severity': severity,
        'source': source,
        'created_at': datetime.now().isoformat(),
        'error': error_description,
        'context': context,
        'fix_suggestion': None,
        'fix_applied': False,
    }
    
    # 让LLM分析并给出修复建议
    try:
        sys.path.insert(0, str(BASE_DIR))
        from brain import call_llm
        prompt = f"""运维问题分析。错误:{error_description} 状态:CPU={context.get('cpu','?')}% 内存={context.get('memory','?')}%
直接输出简短JSON: {{"analysis":"分析","root_cause":"根因","risk":"low/medium/high","need_human":true/false}}"""
        
        resp = call_llm([{'role': 'user', 'content': prompt}])
        # 尝试从响应中提取JSON
        for start_char in ['{']:
            start = resp.find(start_char)
            if start >= 0:
                # 找匹配的右括号
                depth = 0
                for i in range(start, len(resp)):
                    if resp[i] == '{': depth += 1
                    elif resp[i] == '}': depth -= 1
                    if depth == 0:
                        try:
                            ticket['fix_suggestion'] = json.loads(resp[start:i+1])
                            break
                        except:
                            continue
                break
    except Exception as e:
        ticket['fix_suggestion'] = {'error': str(e)}
    
    # 保存工单
    ticket_file = TICKETS_DIR / f'{ticket_id}.json'
    ticket_file.write_text(json.dumps(ticket, ensure_ascii=False, indent=2))
    
    # 写入升级队列（Hermes cron读取）
    escalation_file = BASE_DIR / 'state' / 'dev_tickets.json'
    tickets_queue = []
    if escalation_file.exists():
        try:
            tickets_queue = json.loads(escalation_file.read_text())
        except:
            pass
    
    tickets_queue.append({
        'id': ticket_id,
        'error': error_description,
        'severity': severity,
        'created_at': ticket['created_at'],
        'analysis': ticket.get('fix_suggestion', {}).get('analysis', ''),
        'need_human': ticket.get('fix_suggestion', {}).get('need_human', True),
    })
    
    # 只保留最近20个
    tickets_queue = tickets_queue[-20:]
    escalation_file.write_text(json.dumps(tickets_queue, ensure_ascii=False, indent=1))
    
    return ticket

def collect_dev_context(error_description):
    """收集开发上下文"""
    ctx = {}
    
    def run(cmd):
        try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10).stdout.strip()
        except: return ''
    
    # 基础状态
    ctx['cpu'] = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
    ctx['memory'] = run("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
    ctx['disk'] = run("df / | tail -1 | awk '{print $5}' | tr -d '%'")
    
    # 服务状态
    ctx['services'] = {}
    for svc in ['ttdazi', 'ttdazi-pay', 'aiweb', 'mysql', 'caddy']:
        ctx['services'][svc] = run(f"systemctl is-active {svc}")
    
    # 相关日志
    ctx['recent_logs'] = []
    for log in ['/opt/ttdazi/backend/app/ttdazi.log', '/var/log/ttdazi_pay.log']:
        out = run(f"tail -20 {log} 2>/dev/null | grep -iE 'error|exception|traceback' | tail -3")
        if out:
            ctx['recent_logs'].extend(out.split('\n'))
    ctx['recent_logs'] = [l.strip() for l in ctx['recent_logs'] if l.strip()][:5]
    
    # 可能相关的代码文件
    ctx['related_files'] = []
    keywords = error_description.lower()
    file_map = {
        'mysql': ['backend/app/config.py', 'backend/app/db.py'],
        'payment': ['payment_service/api.py', 'payment_service/wxpay.py'],
        'order': ['backend/app/order.py'],
        'user': ['backend/app/user.py'],
        'login': ['backend/app/wechat_login.py'],
        'companion': ['backend/app/companion.py'],
        'chat': ['backend/app/chat.py'],
    }
    for keyword, files in file_map.items():
        if keyword in keywords:
            ctx['related_files'].extend(files)
    
    # 读取相关文件内容（前50行）
    ctx['file_contents'] = {}
    for f in ctx['related_files'][:3]:
        path = f'/opt/ttdazi/{f}'
        if os.path.exists(path):
            try:
                with open(path) as fh:
                    lines = fh.readlines()[:50]
                    ctx['file_contents'][f] = ''.join(lines)
            except:
                pass
    
    return ctx

def get_tickets():
    """获取所有工单"""
    tickets = []
    for f in sorted(TICKETS_DIR.glob('*.json'), reverse=True):
        try:
            tickets.append(json.loads(f.read_text()))
        except:
            pass
    return tickets

def get_ticket(ticket_id):
    """获取单个工单"""
    ticket_file = TICKETS_DIR / f'{ticket_id}.json'
    if ticket_file.exists():
        return json.loads(ticket_file.read_text())
    return None

def mark_done(ticket_id, result=''):
    """标记工单完成"""
    ticket = get_ticket(ticket_id)
    if ticket:
        ticket['status'] = 'done'
        ticket['completed_at'] = datetime.now().isoformat()
        ticket['result'] = result
        (TICKETS_DIR / f'{ticket_id}.json').write_text(json.dumps(ticket, ensure_ascii=False, indent=2))
        return True
    return False

def get_open_tickets():
    """获取未处理的工单"""
    return [t for t in get_tickets() if t.get('status') == 'open']

# ═══════════════════════════════════════════
# 自动工单（引擎触发）
# ═══════════════════════════════════════════

def auto_ticket_from_engine():
    """引擎检测到无法自动修复的问题时，自动创建工单"""
    try:
        sys.path.insert(0, str(BASE_DIR))
        from engine import load_state
        escalation = load_state('escalation')
        pending = escalation.get('pending', [])
        
        for alert in pending:
            msg = alert.get('message', '')
            # 只为需要人工介入的告警创建工单
            if any(kw in msg for kw in ['重启失败', '无法修复', '需人工', 'critical', 'LLM']):
                # 检查是否已有相同工单
                existing = [t['error'] for t in get_open_tickets()]
                if msg not in existing:
                    ticket = create_ticket(msg, source='engine', severity=alert.get('severity', 'warn'))
                    print(f"📋 自动创建工单: {ticket['id']}")
                    return ticket
    except Exception as e:
        print(f"自动工单失败: {e}")
    return None

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    
    if cmd == 'ticket' and len(sys.argv) > 2:
        desc = ' '.join(sys.argv[2:])
        ticket = create_ticket(desc)
        print(json.dumps(ticket, ensure_ascii=False, indent=2))
    elif cmd == 'status':
        tickets = get_tickets()
        open_count = len([t for t in tickets if t['status'] == 'open'])
        print(json.dumps({'total': len(tickets), 'open': open_count, 'tickets': tickets[:10]}, ensure_ascii=False, indent=2))
    elif cmd == 'context' and len(sys.argv) > 2:
        ticket = get_ticket(sys.argv[2])
        if ticket:
            print(json.dumps(ticket, ensure_ascii=False, indent=2))
        else:
            print(f'工单不存在: {sys.argv[2]}')
    elif cmd == 'done' and len(sys.argv) > 2:
        result = ' '.join(sys.argv[3:]) if len(sys.argv) > 3 else '已修复'
        ok = mark_done(sys.argv[2], result)
        print(f'{"✅ 已标记完成" if ok else "❌ 工单不存在"}')
    elif cmd == 'auto':
        auto_ticket_from_engine()
    else:
        print('用法: ticket "描述" | status | context <id> | done <id> | auto')


def process_ticket_with_agent(ticket_id):
    """用dev_agent处理工单"""
    try:
        sys.path.insert(0, str(BASE_DIR))
        from dev_agent import fix_issue
        ticket = get_ticket(ticket_id)
        if not ticket or ticket['status'] != 'open':
            return None
        
        # 标记为处理中
        ticket['status'] = 'fixing'
        (TICKETS_DIR / f'{ticket_id}.json').write_text(json.dumps(ticket, ensure_ascii=False, indent=2))
        
        # 优先用Codex（更强大），失败回退dev_agent
        result = None
        try:
            import subprocess
            codex_result = subprocess.run(
                ['codex', 'exec', '-m', 'mimo-v2.5-pro', '--', 
                 f'分析这个服务器问题并给出修复方案: {ticket["error"]}'],
                capture_output=True, text=True, timeout=120,
                cwd=str(BASE_DIR.parent)
            )
            if codex_result.returncode == 0 and codex_result.stdout.strip():
                result = {'status': 'fixed', 'source': 'codex', 'output': codex_result.stdout.strip()[:2000]}
        except Exception:
            pass
        
        # Codex失败则用dev_agent
        if not result:
            from dev_agent import fix_issue
            result = fix_issue(ticket['error'])
        
        # 更新工单
        ticket['status'] = 'fixed' if result.get('status') == 'fixed' else 'need_review'
        ticket['fix_result'] = result
        (TICKETS_DIR / f'{ticket_id}.json').write_text(json.dumps(ticket, ensure_ascii=False, indent=2))
        
        return result
    except Exception as e:
        return {'error': str(e)}
