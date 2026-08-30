---
name: production-readiness-audit
description: Systematic full-stack audit for Vue+Flask apps before launch. Scans all backend routes vs frontend API calls, checks HTTP methods, data formats, notification coverage, and admin mirror completeness. Use when user says "检查所有功能" or "上线前审核" or "全面检查" for an existing app.
---

# Production Readiness Audit — Full-Stack API & Feature Verification

Trigger: user asks to "检查所有功能", "全量审计", "上线前审核", "全面检查一遍".

## Workflow

### Phase 1: Backend Route Scan

```python
import re, os

app_dir = '/opt/ttdazi/backend/app'
all_routes = {}

for f in sorted(os.listdir(app_dir)):
    if not f.endswith('.py') or f.startswith('__'):
        continue
    path = os.path.join(app_dir, f)
    with open(path) as fh:
        content = fh.read()
    
    # 1. Find Blueprint + url_prefix
    bp = re.search(r"Blueprint\('(\w+)',\s*__name__,\s*url_prefix='(/api/\w+)'\)", content)
    if not bp:
        continue
    prefix = bp.group(2)
    
    # 2. Find all route + methods
    routes = re.finditer(r"@\w+_bp\.route\('([^']+)',\s*methods=\[([^\]]+)\]", content)
    for m in routes:
        route_path = m.group(1)
        methods = [x.strip().strip("'\"") for x in m.group(2).split(',')]
        full = prefix + route_path
        all_routes[full] = methods

# Also scan main.py for @app.route
with open('/opt/ttdazi/backend/main.py') as fh:
    main_content = fh.read()
for m in re.finditer(r"@app\.route\('([^']+)',\s*methods=\[([^\]]+)\]", main_content):
    all_routes[m.group(1)] = [x.strip().strip("'\"") for x in m.group(2).split(',')]
```

### Phase 2: Frontend API Call Extraction

```python
frontend_calls = []  # [(vue_file, method, path)]
views_dir = '/opt/ttdazi/frontend/src/views'
for root, dirs, files in os.walk(views_dir):
    for f in files:
        if not f.endswith('.vue'):
            continue
        vpath = os.path.relpath(os.path.join(root, f), views_dir)
        with open(os.path.join(root, f)) as fh:
            content = fh.read()
        
        # Static string API calls
        for a in re.finditer(r"api\.(get|post|put|delete)\('/([^']+)'", content):
            frontend_calls.append((vpath, a.group(1).upper(), '/api/' + a.group(2)))
        
        # Template literal API calls (no dynamic parts)
        for a in re.finditer(r"api\.(get|post|put|delete)\(`/([^`$]+)`", content):
            frontend_calls.append((vpath, a.group(1).upper(), '/api/' + a.group(2)))
```

### Phase 3: Cross-Reference

For each frontend call, check if a matching backend route exists.
- Replace path params (`:id`, `:uid`, `<int:cid>`) with regex `\d+`
- Check method compatibility

```python
import re as re2

missing = []
for vue_file, method, path in sorted(frontend_calls):
    matched = False
    for br in backend_routes:
        # Normalize backend route pattern
        br_pat = re2.sub(r':\w+', r'\\d+', br)
        br_pat = br_pat.replace('<int:', '').replace('>', '')
        if re2.match(f'^{br_pat}$', path):
            matched = True
            break
    if not matched:
        missing.append((vue_file, method, path))
```

### Phase 4: Check HTTP Method Mismatch

For matched routes, verify the method used in frontend (get/post/put/delete) matches what the backend accepts.

### Phase 5: Notification Coverage

Check all order/user state transitions have `send_notification()` calls:
- Order: create → pay → complete → confirm → cancel
- User: verify approve/reject, companion audit approve/reject, withdrawal approve/reject

### Phase 6: Admin Mirror Check

Using the `admin-mirror-rule` skill: every user-facing feature must have a corresponding admin management page.

### Phase 7: UI Consistency

- All pages use `.page` / `.header-bar` / `.card-3d` / `.menu-item-3d` global classes
- No Vant Toast/Dialog/ConfirmDialog function calls remain
- Check scoped style for redundant definitions already in global.css
- Admin pages: verify `.admin-main` has `margin-left: 220px` (sidebar is fixed-position, without this the sidebar overlaps content on 8+ admin pages)

### Phase 8: Backend Security Scan

Use a Python script to auto-detect:
1. **Missing auth decorators** — routes that accept user data but lack `@login_required` or `@admin_required`
2. **Bare `except:`** — catches any exception silently, hides bugs. Replace with `except Exception:` 
3. **F-string SQL** — `execute(f"..." )` patterns with user-controlled variables. Verify all dynamic SQL parts use parameterized queries or ALLOWED-field whitelists
4. **Audit log** — verify admin audit operations (withdrawal verify, companion audit, ban-ip) call `audit_log()`

```python
# Scan for bare except
bad = re.findall(r'except\s*:\s*\n\s*(?:pass|#|$)', content)
# Scan for routes missing auth  
routes = re.finditer(r"@\w+_bp\.route\('([^']+)'", content)
for m in routes:
    next_200 = content[m.end():m.end()+200]
    if not any(d in next_200 for d in ['login_required', 'admin_required']):
        # Known public routes that don't need auth
        if route_path not in ['/get', '/list', '/login', '/register']:
            print(f"MISSING AUTH: {route_path}")
```

### Phase 9: Frontend Defensive Code Audit

Use regex to scan all `.vue` files for:
1. **Empty `catch {}`** — silent failures. Replace with `catch(e) { safeToast(e?.message || "操作失败") }` **EXCEPT** for initial-load functions like `refreshCaptcha()` where user can retry by clicking
2. **Template variables that could be undefined** — `item.rating || 5` should be `item.rating ?? 5` (handles rating=0 correctly)
3. **Template references to non-existent fields** — `item.review_count` when API returns `order_count`
4. **API path mismatches** — frontend calls `/banner/create` but backend has `/banners` POST

### Phase 10: Multi-Agent Parallel Audit (Large Projects)

For projects with 50+ pages and 100+ API routes, dispatch 3 subagents in parallel:

```
delegate_task(goal="审计用户端25个页面", context="...")
delegate_task(goal="审计管理端19个页面", context="...") 
delegate_task(goal="审计后端27个API文件", context="...")
```

Each subagent reports issues with severity (🔴🟡🟢). Then aggregate fixes in priority order:
1. 🔴 Auth/crash bugs first (undefined variables, missing decorators)
2. 🔴 Missing API endpoints (frontend calls 404)
3. 🟡 Style inconsistency (wrong global classes, missing margins)
4. 🟢 Minor improvements (toast messages, empty states)

## User Interaction Protocol

When user assigns a task:
1. Start with: **"老板收到，开始安排任务！"**
2. Work the task.
3. When complete, send the task result FIRST, then send a SEPARATE message: **"老板，任务执行完毕，请您审核！"**

Both responses are required and must be separate messages, not merged.

## Common Fixes

| Problem | Fix |
|---------|-----|
| Frontend calls `/banner/create` but backend has `/banners` POST | Fix frontend path or add backend alias |
| Frontend sends POST but backend expects PUT | Change frontend `api.post` → `api.put` |
| Frontend sends `id_card` but backend expects `id_number` | Align field names |
| Scoped CSS duplicates global classes | Remove from scoped, keep only custom styles |
| Missing cancel/audit endpoint | Add endpoint with proper state validation + notification |

## Output Format

Generate a structured report:
- ✅ Backend routes count
- ✅ Frontend pages scanned  
- ❌ Missing APIs (frontend calls with no backend)
- ⚠️ Method mismatches
- ✅ Notification coverage table
- ✅ Admin mirror table
- ❌ UI inconsistencies

## Pitfalls

### Audit Script False Positives

These are common false-positive findings — verify each before reporting:

| Finding | Root Cause | Scanner Fix |
|---------|-----------|-------------|
| `admin.py` missing `from app.admin import admin_required` | `admin_required` is **defined locally in admin.py** (line ~12), not imported | Skip `admin.py` in the import-check loop |
| main.py POST routes reported as 404 | Regex `@app\\.route\\('([^']+)',` captures path but not methods — all routes default to GET | Use `methods=\\[([^\\]]+)\\]` and extract all methods |
| `/api/download-auth` 404 but the route exists | Same as above — main.py POST routes wrongly labelled GET | Fix regex to parse methods |
| Frontend calls `/create-order` but no route found | Router may use different path (`/order/create`) | Match by component file, not path string |
| Frontend calls `/customer-service` but no route found | Router may use shorter path (`/service`) | Same as above |
| `f-string SQL` warnings for `', '.join(fields)` | Safe when `fields` is from FIELD_RULES / ALLOWED whitelist | Confirm whitelist exists before flagging |

### Route Detection Traps

- Template literals (`\\`/banner/${id}/delete\\``) hard to match — extract base path only
- `main.py` routes lack Blueprint prefix — scan separately with full method regex
- Multi-method routes (`methods=['GET','PUT']`) — use `\\[([^\\]]+)\\]` to capture ALL, not just first
- Routes inside `create_app()` factory — regex still works as long as file content is read before scanning

### API Response Shape Traps

- Axios interceptor unwraps `res.data.data` — frontend never sees `{code, data, msg}` wrapper. Verify what the frontend actually receives, not the raw backend response
- `favorite/list` returns `{code:0, data:[...]}` (direct array) instead of `{code:0, data:{list:[...]}}`. Frontend handles with `res || []`
- `list` vs `items` key — admin/messages returns `{items: [...]}` while admin/users/playmates/orders return `{list: [...]}`. Don't assume a single key name

### Frontend Orphan Page Check

Every `.vue` in `views/` needs a route. Cross-check:

```bash
cd frontend/src
for f in views/*.vue views/admin/*.vue views/playmate/*.vue; do
  name=$(basename "$f" .vue)
  if ! grep -q "$name" router/index.js; then echo "⚠️ ORPHAN: $f"; fi
done
```

Common orphan: `Download.vue` — backup download page with no route, users can never reach it.

### Other

- Scoped CSS class mismatch: template uses `pd-*` but scoped CSS defines `.privacy-*`. Run class extraction diff: `grep -oP 'class="[^"]*"' page.vue | tr ' ' '\n' | sort -u` vs `grep -oP '\.[\w-]+' page.vue | sort -u`
- Bare `except:` — silently catches all exceptions including `SystemExit`/`KeyboardInterrupt`. Always use `except Exception:` for operational error handling

## Browser-Unavailable Testing

When `browser_navigate` cannot reach external servers (ERR_BLOCKED_BY_CLIENT, network isolation, proxy blocks), fall back to **token-based curl API testing**.

See `references/offline-api-testing.md` for:
1. Generate JWT tokens via backend Python to bypass captcha
2. Test all public APIs with plain curl
3. Test user APIs with Bearer token
4. Test admin APIs with admin token
5. Response inspection with `python3 -c "import sys,json; d=json.load(sys.stdin); print(str(d)[:300])"`

This covers 95% of "all pages work" verification — the only thing missed is visual rendering and CSS layout, which can be separately verified when network access is restored.
