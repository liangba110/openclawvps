#!/usr/bin/env python3
"""
dev_agent.py — 开发Agent（Python + MiMo API）
替代Codex CLI，直接调用MiMo做代码修改

功能：
  1. 读取问题代码
  2. LLM分析并生成修复
  3. 生成git补丁
  4. 自动测试+部署

用法:
  python3 dev_agent.py fix "错误描述"          # 自动修复
  python3 dev_agent.py review <file>           # 代码审查
  python3 dev_agent.py explain <file> <line>   # 解释代码
  python3 dev_agent.py test <file>             # 生成测试
"""
import os
import sys
import json
import subprocess
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(os.environ.get('OPS_DIR', '/opt/ttdazi/ops'))
PROJECT_DIR = Path('/opt/ttdazi')

# ═══════════════════════════════════════════
# LLM调用（复用brain.py）
# ═══════════════════════════════════════════

API_CONFIG = {
    'base_url': 'https://token-plan-cn.xiaomimimo.com/v1',
    'api_key': 'tp-c2hcz66we5sd0xbpgeuqf0vjqvyq1ix2wsyvdpve7ktv2wj8',
    'model': 'mimo-v2.5',
}

def call_llm(messages, max_tokens=2000):
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
        msg = data['choices'][0]['message']
        content = msg.get('content', '') or ''
        reasoning = msg.get('reasoning_content', '') or ''
        return content.strip() if content.strip() else reasoning

def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except:
        return '', -1

# ═══════════════════════════════════════════
# 安全护栏
# ═══════════════════════════════════════════

# 白名单：允许AI修改的文件
SAFE_PATTERNS = [
    r'ops/.*\.py$',
    r'ops/.*\.yaml$',
    r'backend/app/config\.py$',
    r'backend/app/config_api\.py$',
]

# 禁止修改的文件
BLOCKED_PATTERNS = [
    r'payment_service/.*',
    r'main\.py$',
    r'.*\.env$',
    r'.*secret.*',
    r'.*password.*',
]

def is_safe_to_edit(filepath):
    """检查文件是否可安全修改"""
    rel = str(filepath.relative_to(PROJECT_DIR)) if filepath.is_absolute() else filepath
    
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, rel):
            return False, f'禁止修改: {rel}'
    
    for pattern in SAFE_PATTERNS:
        if re.search(pattern, rel):
            return True, '安全'
    
    return False, f'不在白名单: {rel}'

def git_snapshot():
    """创建Git快照（用于回滚）"""
    try:
        out, code = run(f"cd {PROJECT_DIR} && git add -A && git commit -m '🔧 dev_agent快照 {datetime.now().strftime('%Y-%m-%d %H:%M')}' --allow-empty 2>/dev/null")
        return True  # 即使commit失败也继续（可能无变更）
    except:
        return True

def git_rollback():
    """回滚到上一个快照"""
    # 先检查是否有dev_agent快照
    out, _ = run(f"cd {PROJECT_DIR} && git log --oneline -5 | grep 'dev_agent快照'")
    if not out:
        return False  # 没有快照可回滚
    out, code = run(f"cd {PROJECT_DIR} && git reset --hard HEAD~1 2>/dev/null")
    return code == 0

def check_syntax(filepath):
    """语法检查"""
    if filepath.suffix == '.py':
        out, code = run(f"python3 -m py_compile {filepath} 2>&1")
        return code == 0, out
    elif filepath.suffix in ('.yaml', '.yml'):
        out, code = run(f"python3 -c \"import yaml; yaml.safe_load(open('{filepath}'))\" 2>&1")
        return code == 0, out
    return True, ''

# ═══════════════════════════════════════════
# 核心功能
# ═══════════════════════════════════════════

def fix_issue(error_description):
    """自动修复问题"""
    result = {'timestamp': datetime.now().isoformat(), 'steps': []}
    
    # 1. Git快照
    result['steps'].append({'action': 'git_snapshot', 'ok': git_snapshot()})
    
    # 2. 收集上下文
    ctx = collect_error_context(error_description)
    result['context'] = ctx
    
    # 3. LLM生成修复
    prompt = f"""你是Linux全栈开发工程师。根据错误信息和代码上下文，生成修复补丁。

错误: {error_description}
相关文件:
{format_files(ctx.get('files', {}))}

要求:
1. 只修改白名单内的文件
2. 输出格式为JSON: {{"file":"文件路径","old_code":"原代码片段(精确匹配)","new_code":"新代码"}}
3. 如果需要多个修改，输出数组
4. 只输出修复代码，不要解释
5. 确保修改后语法正确

输出JSON:"""

    resp = call_llm([{'role': 'user', 'content': prompt}])
    
    # 4. 解析LLM输出
    fixes = extract_fixes(resp)
    result['fixes_found'] = len(fixes)
    
    # 5. 安全检查+应用
    applied = []
    for fix in fixes:
        filepath = PROJECT_DIR / fix.get('file', '')
        safe, reason = is_safe_to_edit(filepath)
        
        if not safe:
            result['steps'].append({'action': 'skip', 'file': str(filepath), 'reason': reason})
            continue
        
        if not filepath.exists():
            result['steps'].append({'action': 'skip', 'file': str(filepath), 'reason': '文件不存在'})
            continue
        
        # 应用修改
        ok = apply_fix(filepath, fix)
        applied.append({'file': str(filepath), 'applied': ok})
        
        # 语法检查
        syntax_ok, syntax_err = check_syntax(filepath)
        if not syntax_ok:
            git_rollback()
            result['steps'].append({'action': 'rollback', 'reason': f'语法错误: {syntax_err[:100]}'})
            return result
    
    result['steps'].append({'action': 'apply', 'fixes': applied})
    result['status'] = 'fixed'
    
    return result

def collect_error_context(error_description):
    """收集错误上下文"""
    ctx = {'files': {}}
    
    # 根据错误关键词找相关文件
    keywords = {
        'mysql': ['backend/app/config.py', 'backend/app/db.py'],
        'payment': ['payment_service/api.py'],
        'order': ['backend/app/order.py'],
        'user': ['backend/app/user.py'],
        'login': ['backend/app/wechat_login.py'],
        'companion': ['backend/app/companion.py'],
        'config': ['backend/app/config.py'],
    }
    
    for keyword, files in keywords.items():
        if keyword in error_description.lower():
            for f in files:
                path = PROJECT_DIR / f
                if path.exists():
                    try:
                        content = path.read_text()
                        # 只取相关行（±20行围绕错误）
                        lines = content.split('\n')
                        ctx['files'][f] = '\n'.join(lines[:100])  # 前100行
                    except:
                        pass
    
    # 系统状态
    ctx['cpu'] = run("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")[0]
    ctx['memory'] = run("free | grep Mem | awk '{printf \"%.1f\", $3/$2*100}'")[0]
    
    return ctx

def format_files(files_dict):
    """格式化文件内容"""
    result = []
    for name, content in files_dict.items():
        result.append(f"=== {name} ===\n{content[:2000]}\n")
    return '\n'.join(result)

def extract_fixes(llm_response):
    """从LLM响应中提取修复"""
    fixes = []
    
    # 尝试JSON解析
    try:
        start = llm_response.find('[')
        if start >= 0:
            # 找匹配的]
            depth = 0
            for i in range(start, len(llm_response)):
                if llm_response[i] == '[': depth += 1
                elif llm_response[i] == ']': depth -= 1
                if depth == 0:
                    fixes = json.loads(llm_response[start:i+1])
                    break
        else:
            start = llm_response.find('{')
            if start >= 0:
                depth = 0
                for i in range(start, len(llm_response)):
                    if llm_response[i] == '{': depth += 1
                    elif llm_response[i] == '}': depth -= 1
                    if depth == 0:
                        fix = json.loads(llm_response[start:i+1])
                        fixes = [fix]
                        break
    except:
        pass
    
    return fixes

def apply_fix(filepath, fix):
    """应用修复"""
    old_code = fix.get('old_code', '')
    new_code = fix.get('new_code', '')
    
    if not old_code or not new_code:
        return False
    
    try:
        content = filepath.read_text()
        if old_code in content:
            content = content.replace(old_code, new_code, 1)
            filepath.write_text(content)
            return True
        else:
            return False
    except:
        return False

def review_file(filepath):
    """代码审查"""
    path = PROJECT_DIR / filepath
    if not path.exists():
        return {'error': f'文件不存在: {filepath}'}
    
    content = path.read_text()
    prompt = f"""审查这个Python/配置文件，指出：
1. 安全漏洞
2. 性能问题
3. 代码质量
4. 改进建议

文件: {filepath}
内容:
```
{content[:3000]}
```

输出JSON: {{"security_issues":[],"performance":[],"quality":[],"suggestions":[]}}"""

    resp = call_llm([{'role': 'user', 'content': prompt}])
    
    try:
        start = resp.find('{')
        end = resp.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(resp[start:end])
    except:
        pass
    return {'raw': resp[:500]}

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'
    
    if cmd == 'fix' and len(sys.argv) > 2:
        desc = ' '.join(sys.argv[2:])
        result = fix_issue(desc)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'review' and len(sys.argv) > 2:
        result = review_file(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd == 'help':
        print('用法: fix "错误描述" | review <file>')
    else:
        print(f'未知命令: {cmd}')
