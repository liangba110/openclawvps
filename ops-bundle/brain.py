from brain_v2 import call_llm_safe
def call_llm_with_fallback(messages, max_tokens=500):
    """LLM调用（带fallback到本地规则）"""
    try:
        return call_llm(messages, max_tokens)
    except Exception as e:
        return f'LLM调用失败({str(e)[:50]})，建议检查API连接或使用本地规则'

#!/usr/bin/env python3
"""
brain.py — LLM决策引擎（MiMo推理模型适配版）
"""
import os, sys, json, subprocess
from pathlib import Path

API_CONFIG = {
    'base_url': 'https://token-plan-cn.xiaomimimo.com/v1',
    'api_key': os.environ.get('MIMO_API_KEY', ''),
    'model': 'mimo-v2.5',
}

def call_llm(messages, max_tokens=800):
    import urllib.request
    payload = json.dumps({
        'model': API_CONFIG['model'],
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': 0,
    }).encode('utf-8')
    req = urllib.request.Request(
        f"{API_CONFIG['base_url']}/chat/completions",
        data=payload,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_CONFIG["api_key"]}'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            msg = data['choices'][0]['message']
            content = msg.get('content', '') or ''
            reasoning = msg.get('reasoning_content', '') or ''
            # 优先content，没有则用reasoning
            return content.strip() if content.strip() else reasoning
    except Exception as e:
        return f'LLM调用失败: {e}'

def get_status():
    """获取系统状态摘要"""
    def run(cmd):
        try: return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8).stdout.strip()
        except: return ''
    svcs = {s: run(f"systemctl is-active {s}") for s in ['ttdazi','ttdazi-pay','aiweb','mysql','caddy']}
    down = [s for s,v in svcs.items() if v != 'active']
    cpu = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
    mem = run("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")
    disk = run("df / | tail -1 | awk '{print $5}' | tr -d '%'")
    import shlex
    mp = shlex.quote(os.environ.get('MYSQL_PASSWORD', ''))
    mysql = run(f"mysql -uroot -p{mp} -N -e \"SHOW STATUS LIKE 'Threads_connected';\" | awk '{print $2}'")
    return f"CPU={cpu}% 内存={mem}% 磁盘={disk}% MySQL连接={mysql} 宕机服务={down or '无'}"

def decide(issue):
    status = get_status()
    prompt = f"""服务器运维。状态:{status}
问题:{issue}
直接输出JSON修复方案，不要解释：{{"actions":[{{"cmd":"shell命令","reason":"原因"}}],"risk":"low/medium/high"}}"""
    resp = call_llm([{'role':'user','content':prompt}])
    # 提取JSON
    try:
        # 安全提取JSON（处理嵌套）
        import re
        # 找到第一个{和最后一个}
        start = resp.find('{')
        if start >= 0:
            depth = 0
            end = start
            for i in range(start, len(resp)):
                if resp[i] == '{': depth += 1
                elif resp[i] == '}': depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            return json.loads(resp[start:end])
    except: pass
    return {'raw': resp[:500], 'analysis': resp[:500]}

def analyze():
    status = get_status()
    prompt = f"""服务器状态:{status}
分析是否有异常，有则输出修复方案JSON，无则输出{{"status":"ok"}}"""
    resp = call_llm([{'role':'user','content':prompt}])
    try:
        # 安全提取JSON（处理嵌套）
        import re
        # 找到第一个{和最后一个}
        start = resp.find('{')
        if start >= 0:
            depth = 0
            end = start
            for i in range(start, len(resp)):
                if resp[i] == '{': depth += 1
                elif resp[i] == '}': depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            return json.loads(resp[start:end])
    except: pass
    return {'analysis': resp[:500]}

def explain(error_text):
    prompt = f"""解释Linux错误并给修复命令。错误:{error_text[:300]}
输出JSON：{{"explanation":"含义","fixes":[{{"cmd":"命令","reason":"原因"}}]}}"""
    resp = call_llm([{'role':'user','content':prompt}])
    try:
        # 安全提取JSON（处理嵌套）
        import re
        # 找到第一个{和最后一个}
        start = resp.find('{')
        if start >= 0:
            depth = 0
            end = start
            for i in range(start, len(resp)):
                if resp[i] == '{': depth += 1
                elif resp[i] == '}': depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            return json.loads(resp[start:end])
    except: pass
    return {'explanation': resp[:500]}

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'analyze'
    if cmd == 'decide': print(json.dumps(decide(' '.join(sys.argv[2:])), ensure_ascii=False, indent=2))
    elif cmd == 'analyze': print(json.dumps(analyze(), ensure_ascii=False, indent=2))
    elif cmd == 'explain': print(json.dumps(explain(' '.join(sys.argv[2:])), ensure_ascii=False, indent=2))
    else: print('用法: decide "问题" | analyze | explain "错误"')
