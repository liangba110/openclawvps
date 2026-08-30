#!/usr/bin/env python3
"""
同途搭子全栈预上线审计脚本
检查前端→后端404端点、认证装饰器、字段白名单、安全漏洞

用法:
    python3 /opt/ttdazi/scripts/fullstack-audit.py

输出: /tmp/ttdazi-audit-report.md
"""
import re, os, json, subprocess, sys
from collections import defaultdict

BASE = '/opt/ttdazi'
FRONTEND_SRC = os.path.join(BASE, 'frontend', 'src')
BACKEND_APP = os.path.join(BASE, 'backend', 'app')
BACKEND_MAIN = os.path.join(BASE, 'backend', 'main.py')

ISSUES = []  # (file, severity, category, detail)

def log(file, severity, category, detail):
    ISSUES.append((file, severity, category, detail))

# ── 1. Frontend → Backend API 404 Check ──
def check_api_404():
    print("[1/6] 检查前端→后端404端点...")
    backend_routes = set()
    for f in os.listdir(BACKEND_APP):
        if not f.endswith('.py') or f.startswith('__'): continue
        with open(os.path.join(BACKEND_APP, f)) as fh:
            content = fh.read()
        bp = re.search(r"Blueprint\('(\w+)',\s*__name__,\s*url_prefix='(/api/\w+)'\)", content)
        if not bp: continue
        prefix = bp.group(2)
        for m in re.finditer(r"@\w+_bp\.route\('([^']+)',\s*methods=\[([^\]]+)\]", content):
            route = m.group(1).replace('<int:', ':').replace('>', '')
            for meth in re.findall(r"'(\w+)'", m.group(2)):
                backend_routes.add((prefix + route, meth.upper()))
    # main.py routes (capture methods too — don't default to GET!)
    with open(BACKEND_MAIN) as fh:
        main_content = fh.read()
    for m in re.finditer(r"@app\.route\('([^']+)',\s*methods=\[([^\]]+)\]", main_content):
        route = m.group(1).replace('<path:', ':').replace('>', '')
        for meth in re.findall(r"'(\w+)'", m.group(2)):
            backend_routes.add((route, meth.upper()))

    # Frontend API calls
    for root, dirs, files in os.walk(FRONTEND_SRC):
        for f in files:
            if not f.endswith('.vue'): continue
            vpath = os.path.relpath(os.path.join(root, f), FRONTEND_SRC)
            with open(os.path.join(root, f)) as fh:
                content = fh.read()
            for a in re.finditer(r"api\.(get|post|put|delete)\('/([^']+)'", content):
                path = '/api/' + a.group(2)
                method = a.group(1).upper()
                matched = False
                for br, bm in backend_routes:
                    br_pat = re.sub(r':\w+', r'\\d+', br)
                    if re.match(f'^{br_pat}$', path) and method == bm:
                        matched = True; break
                if not matched:
                    log(vpath, '🔴', '404端点', f"{method} {path}")

# ── 2. @admin_required Coverage ──
def check_admin_auth():
    print("[2/6] 检查admin路由认证装饰器...")
    with open(os.path.join(BACKEND_APP, 'admin.py')) as fh:
        content = fh.read()
    for m in re.finditer(r"@admin_bp\.route\('([^']+)',", content):
        route = m.group(1)
        pos = m.end()
        next200 = content[pos:pos+200]
        if '@admin_required' not in next200 and route != '/path' and route != '/login' and route != '/register':
            log('admin.py', '🔴', '认证缺失', f"@admin_required: {route}")

# ── 3. admin_required import ──
def check_admin_import():
    print("[3/6] 检查admin_required导入...")
    for f in os.listdir(BACKEND_APP):
        if not f.endswith('.py') or f.startswith('__') or f == 'admin.py': continue
        with open(os.path.join(BACKEND_APP, f)) as fh:
            content = fh.read()
        if '@admin_required' in content and 'from app.admin import admin_required' not in content:
            log(f, '🔴', '导入缺失', 'admin_required 未导入')

# ── 4. Bare except ──
def check_bare_except():
    print("[4/6] 检查bare except...")
    for f in os.listdir(BACKEND_APP):
        if not f.endswith('.py') or f.startswith('__'): continue
        with open(os.path.join(BACKEND_APP, f)) as fh:
            content = fh.read()
        if re.search(r'^[ \t]*except\s*:[ \t]*$', content, re.MULTILINE):
            log(f, '🔴', '裸except', 'except: 无异常类型')

# ── 5. f-string SQL risk ──
def check_fstring_sql():
    print("[5/6] 检查f-string SQL...")
    for f in os.listdir(BACKEND_APP):
        if not f.endswith('.py') or f.startswith('__'): continue
        with open(os.path.join(BACKEND_APP, f)) as fh:
            content = fh.read()
        # Only flag if using f-string with non-field variables
        for m in re.finditer(r"execute\(f[\"']", content):
            sql = content[m.start():m.start()+200]
            vars_in_f = re.findall(r'\{([^}]+)\}', sql)
            for v in vars_in_f:
                v = v.strip()
                if v not in ('where', 'where_clause', 'order_by', 'order_clause', 'set_clause',
                             'fields', 'params', 'limit', 'offset', 'page_size'):
                    log(f, '🟡', 'f-string SQL', f"可能注入风险: {v}")

# ── 6. SMS pwd hardcoded ──
def check_hardcoded_secrets():
    print("[6/6] 检查硬编码秘密...")
    for f in os.listdir(BACKEND_APP):
        if not f.endswith('.py') or f.startswith('__'): continue
        with open(os.path.join(BACKEND_APP, f)) as fh:
            content = fh.read()
        smtp = re.findall(r'smtp\.\w+\s*=\s*[\"\'][^\"\']+[\"\']', content)
        for s in smtp:
            log(f, '🟡', '硬编码', s[:60])

if __name__ == '__main__':
    check_api_404()
    check_admin_auth()
    check_admin_import()
    check_bare_except()
    check_fstring_sql()
    check_hardcoded_secrets()

    # Generate report
    report = "# 同途搭子全栈预上线审计报告\n\n"
    report += f"检查时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    report += "| 文件 | 严重程度 | 类型 | 详情 |\n|------|---------|------|------|\n"
    for f, sev, cat, det in ISSUES:
        report += f"| {f} | {sev} | {cat} | {det} |\n"

    sev_count = defaultdict(int)
    for _, sev, _, _ in ISSUES:
        sev_count[sev] += 1
    report += f"\n## 汇总\n- 🔴 严重: {sev_count.get('🔴', 0)}\n- 🟡 中等: {sev_count.get('🟡', 0)}\n\n"
    if sev_count.get('🔴', 0) == 0:
        report += "**✅ 无严重问题，可以上线**\n"
    else:
        report += f"**⚠️ {sev_count.get('🔴', 0)} 个严重问题需修复**\n"

    report_path = '/tmp/ttdazi-audit-report.md'
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"\n报告已输出至 {report_path}")
    print(f"🔴 {sev_count.get('🔴', 0)}  🟡 {sev_count.get('🟡', 0)}")
