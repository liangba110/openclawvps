---
name: fullstack-api-audit
description: Systematic full-stack API audit methodology — scan frontend API calls vs backend routes, find missing endpoints, method mismatches, data format incompatibilities, and feature gaps. Works for any Vue/React + Flask/FastAPI/Express project.
trigger: |
  User asks to "check all APIs", "audit the whole site", "make sure everything works",
  "全面检查", "全量审计", or equivalents suggesting a comprehensive end-to-end verification.
  Also use before production launch or after major refactoring.
references:
  - references/backend-security-checklist.md — Backend auth, bare except, SQL injection, and variable scope issues found during real audits
  - references/registration-bugs-found-during-audit.md — Registration flow bugs: password validation, email format, SMTP 550, bytecode cache, undefined variables, double updates
  - references/regex-search-files-patterns.md — Lightweight tool-based alternative: use Hermes search_files instead of Python scripts
---

# Full-Stack API Audit Methodology

A systematic, scriptable approach to auditing frontend-backend API alignment.

## Workflow

### 1. Scan Backend Routes

Extract all route definitions from Python/Node backend files.

```python
import re, os

app_dir = '/opt/ttdazi/backend/app'
backend_routes = set()

for f in sorted(os.listdir(app_dir)):
    if not f.endswith('.py') or f.startswith('__'):
        continue
    with open(os.path.join(app_dir, f)) as fh:
        content = fh.read()
    
    # Get Blueprint prefix
    bp = re.search(r"Blueprint\('(\w+)',\s*__name__,\s*url_prefix='(/api/\w+)'\)", content)
    if not bp:
        continue
    prefix = bp.group(2)
    
    # Find all route definitions with methods
    for m in re.finditer(r"@\w+_bp\.route\('([^']+)',\s*methods=\[([^\]]+)\]", content):
        route = m.group(1)
        methods = [x.strip().strip("'\"") for x in m.group(2).split(',')]
        route_normalized = re.sub(r'<int:(\w+)>', r':\1', route).replace('<', '').replace('>', '')
        full = prefix + route_normalized
        backend_routes.add(full)
```

### 2. Scan Frontend API Calls

Extract all `api.get/post/put/delete` calls from Vue/React files.

```python
frontend_calls = []
views_dir = '/opt/ttdazi/frontend/src/views'

for root, dirs, files in os.walk(views_dir):
    for f in files:
        if not f.endswith(('.vue', '.js', '.ts')):
            continue
        vpath = os.path.relpath(os.path.join(root, f), views_dir)
        with open(os.path.join(root, f)) as fh:
            content = fh.read()
        
        # Static string paths: api.get('/user/info')
        for a in re.finditer(r"api\.(get|post|put|delete)\('/([^']+)'", content):
            frontend_calls.append((vpath, a.group(1).upper(), '/api/' + a.group(2)))
        
        # Template literal paths: api.put(`/admin/banners/${id}`)
        # Only match static parts, skip dynamic segments
        for a in re.finditer(r"api\.(get|post|put|delete)\(`/([^`$]+)`", content):
            frontend_calls.append((vpath, a.group(1).upper(), '/api/' + a.group(2)))
```

### 3. Cross-Reference & Find Gaps

For each frontend call, check if a matching backend route exists. Handle path parameters.

```python
missing = []
for vue_file, method, path in frontend_calls:
    matched = False
    for br in backend_routes:
        # Normalize backend route pattern for matching
        br_pat = re.sub(r':\w+', r'[^/]+', br)  # :id → [^/]+
        if re.match(f'^{br_pat}$', path):
            matched = True
            break
    if not matched:
        missing.append((vue_file, method, path))
```

### 4. Additional Checks Beyond Path Matching

| Check | Method |
|-------|--------|
| **Method mismatch** | Compare frontend HTTP method vs backend `methods=[]` |
| **Data format** | Check backend returns `{list,total}` vs frontend expects array |
| **Multi-method routes** | Routes with `['GET', 'PUT']` are missed by simple scanners — check separately |
| **Admin mirror rule** | Every user-facing feature → verify admin management page exists |
| **Auth decorators** | Check if sensitive endpoints have `@login_required` / `@admin_required` |

### 5. Multi-Method Routes (Missed by Simple Scanner)

Routes with multiple methods (`methods=['GET', 'PUT']`) break single-method regex scanners.
Check these separately:

```python
multi = [r for r in all_routes if len(r[2]) > 1]
```

## Report Structure

Generate a report with this structure:

```
## Audit Report

### Missing APIs (frontend calls with no backend route)
| File | Method | Path | Fix |
|------|--------|------|-----|

### Method Mismatches
| File | Frontend Method | Backend Method | Path |

### Data Format Issues
| Endpoint | Backend Returns | Frontend Expects |

### Unused Backend Routes (not called by any frontend)
| Path | Method | Status |
```

## Advanced: 3-Way Parallel Audit (Full Coverage)

For comprehensive audits covering user-facing pages, admin pages, AND backend APIs simultaneously, use parallel subagents:

### Dispatch Pattern

```python
delegate_task(
    goal="审计用户端所有页面：模板渲染、数据显示、交互逻辑、样式统一性",
    context="逐页检查：空catch、样式统一性、数据显示条件缺失、safeToast使用",
)
delegate_task(
    goal="审计管理端所有页面：API映射、数据展示、交互逻辑、布局统一性",
    context="逐页检查：API路径匹配、admin-layout/AdminSidebar统一布局、分页、字段命名",
)
delegate_task(
    goal="全面审计后端API文件：返回值格式、字段命名、参数验证、安全性",
    context="逐文件检查：认证装饰器缺失、bare except、f-string SQL、conn作用域、audit_log",
)
```

### Audit Categories & Output

| Category | What to Check | Output Format |
|----------|--------------|---------------|
| 🔴 缺失 API | 前端调了后端没有 | File + Method + Path |
| 🔴 HTTP Method 不匹配 | POST vs PUT/DELETE | Fix suggestion |
| 🔴 认证缺失 | 路由无 auth 装饰器 | Route list |
| 🟡 数据格式不一致 | 字段名、返回结构 | Backend vs Frontend |
| 🟡 bare except | `except: pass` 吞错误 | File + line |
| 🟡 空 catch | 前端 `catch {}` 无 toast | File + context |
| 🟢 隐藏功能 | 后端有但前端未调用的路由 | Route list |

### Backend Security Checklist (Per-File)

For each `.py` file in `backend/app/`:

1. **Auth decorators**: Every route has @login_required or @admin_required (except public ones like /login, /list, /captcha)
2. **Bare excepts**: All `except:` changed to `except Exception:`
3. **f-string SQL**: Check if variables are from ALLOWED white-list, not raw user input
4. **conn scope**: `conn` variable defined inside `if` block but used outside — this crashes with NameError
5. **audit_log**: Admin audit operations should call `audit_log()`
6. **Return format**: All routes use `success()` or `fail()` consistently
7. **Field whitelist**: Update/create operations validate fields against ALLOWED list

### Common Frontend Issues Found During Audits

| Issue | Example | Fix |
|-------|---------|-----|
| Empty catch | `catch {}` → no error feedback | `catch(e) { safeToast(e?.message) }` |
| Undefined variable in template | `item.review_count` → undefined | Fix field name or use `|| 0` |
| Rating=0 shows 5 stars | `item.rating || 5` → 0 is falsy | Use `?? 5` (nullish coalescing) |
| Missing global styles | Custom `.page-container` instead of `.page` | Use global classes |
| Sidebar overlap | Admin pages missing `margin-left: 220px` | Add to `.admin-main` |
| safeConfirm not imported | Using `safeConfirm()` without import | Add import line |
| Local `success`/`fail` defined | File defines own instead of importing from utils | Remove duplicate, use imported |

## Pitfalls & Common Fixes

### Path Conventions

| Frontend (wrong) | Backend (correct) | Fix |
|------------------|-------------------|-----|
| `/admin/banner/create` (POST) | `/admin/banners` (POST) | Strip `/create` |
| `/admin/banner/5/update` (POST) | `/admin/banners/5` (PUT) | Method + path |
| `/admin/banner/5/delete` (POST) | `/admin/banners/5` (DELETE) | Method |
| `/review/v2/verify/*` | `/user/verify` | Wrong module entirely |

### Route Registration Traps

- **Import naming**: `from app.agreement import agreement_bp` — NOT `agreement_api`
- **Circular imports**: `from app.admin import admin_required` — `admin_required` lives in `admin.py`, not `utils.py`
- **Method mismatch**: Frontend uses `api.post()` but backend expects `PUT` (e.g., `/playmate/status`)
- **Blueprint prefix**: `url_prefix='/api/playmate'` → frontend calls `/playmate/xxx`

### Data Format Mismatches

- Backend returns `{'list': [...], 'total': N}` but frontend iterates the response directly as an array
- Backend expects `id_number` but frontend sends `id_card`
- Backend returns Decimal type (not JSON-serializable) — cast to float
- Axios interceptor returns `res.data.data` — verify data structure matches

### Scope Bugs

- Flask: `conn` variable defined inside `if 'phone' in data:` block but used outside it
  → Solution: always get connection at function start or inside the `try` block
