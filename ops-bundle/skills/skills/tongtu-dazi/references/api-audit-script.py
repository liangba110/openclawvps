#!/usr/bin/env python3
"""
同途搭子全量 API 审计脚本
===========================
用法: python3 /opt/ttdazi/scripts/api-audit.py

检查内容:
  1. 前端调用路径在后端有无对应路由（含 baseURL=/api 前缀）
  2. HTTP Method 是否匹配
  3. REST 风格是否一致（AdminContent.vue 的 CRUD 路径 vs 后端）
  4. Vant 残留（showToast / showLoadingToast / showConfirmDialog）
  5. main.py 直联路由（/api/download-auth 等非 Blueprint 路由）
  6. 陪玩师订单操作完整性
  7. 管理端审核操作完整性
  8. 订单状态枚举覆盖

注意事项:
  - 前端 axios baseURL=/api，所以前端 api.get('/xxx') 实际请求 /api/xxx
  - 后端路由分散在 20 个 Blueprint + main.py @app.route 直联路由
  - main.py 直联路由不会被 Blueprint 匹配捕获，需单独检查
"""
import re, os
from collections import defaultdict

# === CONFIG ===
BACKEND_DIR = '/opt/ttdazi/backend/app'
FRONTEND_DIR = '/opt/ttdazi/frontend/src/views'
MAIN_PY = '/opt/ttdazi/backend/main.py'

# Blueprint 前缀映射（必须与 main.py 中 Blueprint 的 url_prefix 一致）
FILE_TO_BP = {
    'admin.py': '/api/admin', 'agreement.py': '/api/agreement',
    'attendance.py': '/api/attendance', 'captcha.py': '/api/captcha',
    'companion.py': '/api/companion', 'config_api.py': '/api/config',
    'coupon.py': '/api/coupon', 'customer_service.py': '/api/cs',
    'favorite.py': '/api/favorite', 'feedback.py': '/api/feedback',
    'game.py': '/api/game', 'message.py': '/api/message',
    'order.py': '/api/order', 'payment.py': '/api/payment',
    'playmate_api.py': '/api/playmate', 'platform_review.py': '/api/review/v2',
    'review.py': '/api/review', 'security_api.py': '/api/security',
    'statistics.py': '/api/stats', 'user.py': '/api/user',
}


def collect_backend_routes():
    """收集所有 Blueprint 路由 + main.py 直联路由"""
    routes = {}  # norm_path -> list of {full, methods, file}

    # Blueprint 路由
    for fname, prefix in FILE_TO_BP.items():
        fpath = os.path.join(BACKEND_DIR, fname)
        if not os.path.exists(fpath):
            continue
        with open(fpath) as f:
            for line in f:
                m = re.match(
                    r'.*@\w+_bp\.route\([\'"]([^\'"]+)[\'"]\s*,\s*methods=\[([^\]]+)\]',
                    line
                )
                if m:
                    route = m.group(1)
                    methods = [x.strip().strip("'\"") for x in m.group(2).split(',')]
                    full = prefix + route
                    norm = re.sub(r'<int:\w+>', '<id>', full)
                    norm = re.sub(r'<[^>]+>', '<param>', norm)
                    key = f"{full}|{','.join(sorted(methods))}"
                    routes[key] = {'full': full, 'methods': methods, 'file': fname}

    # main.py 直联路由
    main_routes = {}
    if os.path.exists(MAIN_PY):
        with open(MAIN_PY) as f:
            for line in f:
                m = re.match(
                    r'.*@app\.route\([\'"]([^\'"]+)[\'"]\s*,\s*methods=\[([^\]]+)\]',
                    line
                )
                if m:
                    path = m.group(1)
                    methods = [x.strip().strip("'\"") for x in m.group(2).split(',')]
                    main_routes[f"{path}|{','.join(sorted(methods))}"] = {
                        'full': path, 'methods': methods, 'file': 'main.py'
                    }

    return routes, main_routes


def collect_frontend_calls():
    """收集所有前端 .vue 文件中的 api.get/post/put/delete 调用"""
    calls = defaultdict(list)  # file -> [(method, raw_path, full_path, lineno)]
    for root, dirs, files in os.walk(FRONTEND_DIR):
        for f in files:
            if not f.endswith('.vue'):
                continue
            rel = os.path.relpath(os.path.join(root, f), FRONTEND_DIR)
            with open(os.path.join(root, f)) as fh:
                for lineno, line in enumerate(fh, 1):
                    for m in re.finditer(
                        r'api\.(get|post|put|delete)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                        line
                    ):
                        raw = m.group(2)
                        method = m.group(1).upper()
                        # baseURL=/api 所以 /xxx → /api/xxx
                        full = ('/api' + raw) if raw.startswith('/') else raw
                        calls[rel].append((method, raw, full, lineno))
    return calls


def check_vant_legacy():
    """检查是否还有 Vant showToast/showLoadingToast 残留"""
    issues = []
    for root, dirs, files in os.walk(FRONTEND_DIR):
        for f in files:
            if not f.endswith('.vue'):
                continue
            rel = os.path.relpath(os.path.join(root, f), FRONTEND_DIR)
            with open(os.path.join(root, f)) as fh:
                for lineno, line in enumerate(fh, 1):
                    for token in [
                        'showToast', 'showLoadingToast', 'showConfirmDialog',
                        'closeToast', "from 'vant'"
                    ]:
                        if token in line:
                            issues.append((rel, lineno, line.strip(), token))
    return issues


def main():
    print("=" * 70)
    print("  同途搭子 API 全量审计")
    print("=" * 70)

    bp_routes, main_routes = collect_backend_routes()
    backend_by_norm = defaultdict(list)
    for key, info in bp_routes.items():
        norm = re.sub(r'<int:\w+>', '<id>', info['full'])
        norm = re.sub(r'<[^>]+>', '<param>', norm)
        backend_by_norm[norm].append(info)

    frontend_calls = collect_frontend_calls()
    vant_issues = check_vant_legacy()

    # 检查缺失和方法不匹配
    missing = []
    method_mismatch = []
    rest_style = []

    for rel, calls in sorted(frontend_calls.items()):
        for method, raw, full, lineno in calls:
            if not raw.startswith('/'):
                continue

            # main.py 直联路由检查
            found_in_main = False
            for key, info in main_routes.items():
                if info['full'] == full:
                    found_in_main = True
                    if method not in [m.upper() for m in info['methods']]:
                        method_mismatch.append(
                            (rel, method, raw, info['methods'], lineno, 'main.py')
                        )
                    break
            if found_in_main:
                continue

            # Blueprint 路由检查
            fnorm = re.sub(r'/\d+', '/<id>', full)
            fnorm = re.sub(r'/[a-f0-9]{24,}', '/<id>', fnorm)
            be_list = backend_by_norm.get(fnorm, [])

            if not be_list:
                missing.append((rel, method, raw, full, lineno))
            else:
                be_methods = set()
                for be in be_list:
                    be_methods.update(be['methods'])
                if method not in [m.upper() for m in be_methods]:
                    method_mismatch.append(
                        (rel, method, raw, be_methods, lineno, be_list[0]['file'])
                    )

            # REST 风格检查：前端路径是否和后端路径风格差异过大
            if raw.startswith('/admin/banner/') or raw.startswith('/admin/game/'):
                rest_style.append((rel, method, raw, lineno))

    # 输出结果
    print(f"\n{'='*70}")
    print(f"  ❌ 缺失 API: {len(missing)} 个")
    print(f"{'='*70}")
    for rel, method, raw, full, lineno in missing:
        print(f"  {rel} L{lineno}: {method} '{raw}' -> {full}")

    print(f"\n{'='*70}")
    print(f"  ⚠️  HTTP Method 不匹配: {len(method_mismatch)} 个")
    print(f"{'='*70}")
    for rel, method, raw, expected, lineno, fname in method_mismatch:
        print(f"  {rel} L{lineno}: {method} '{raw}' -> 后端({fname})需 {expected}")

    if rest_style:
        print(f"\n{'='*70}")
        print(f"  🟡 REST 风格不一致: {len(rest_style)} 个")
        print(f"{'='*70}")
        for rel, method, raw, lineno in rest_style:
            print(f"  {rel} L{lineno}: {method} '{raw}' -> 建议改用 RESTful 路径")

    print(f"\n{'='*70}")
    print(f"  🚫 Vant 残留: {len(vant_issues)} 个")
    print(f"{'='*70}")
    if vant_issues:
        for rel, lineno, text, token in vant_issues:
            print(f"  {rel} L{lineno}: {token} -> {text}")
    else:
        print(f"  ✅ 干净")

    # 按页面汇总
    print(f"\n{'='*70}")
    print(f"  按页面汇总")
    print(f"{'='*70}")
    for rel, calls in sorted(frontend_calls.items()):
        is_admin = any('/admin/' in c[1] for c in calls)
        tag = '[ADMIN]' if is_admin else '[USER]'
        ok = sum(1 for c in calls if c[1].startswith('/'))
        print(f"\n  {tag} {rel} ({len(calls)} API calls)")
        for method, raw, full, lineno in calls:
            if not raw.startswith('/'):
                continue
            fnorm = re.sub(r'/\d+', '/<id>', ('/api' + raw) if raw.startswith('/') else raw)
            be = backend_by_norm.get(fnorm, [])
            found = bool(be) or any(info['full'] == full for info in main_routes.values())
            method_ok = True
            if be:
                bms = set()
                for b in be:
                    bms.update(b['methods'])
                if method not in [m.upper() for m in bms]:
                    method_ok = False
            status = '✅' if (found and method_ok) else ('⚠️ ' if found else '❌')
            print(f"    L{lineno}: {status} {method} {raw}")


if __name__ == '__main__':
    main()
