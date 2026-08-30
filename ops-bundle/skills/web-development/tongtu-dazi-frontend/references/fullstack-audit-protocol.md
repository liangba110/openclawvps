# 全量审计协议 — 前后端API映射 + 后端安全

## 前端API映射审计

### 扫描命令
```bash
# 1. 扫出后端所有路由
cd /opt/ttdazi/backend && PYTHONPATH="..." python3.12 -c "
import re, os
routes = set()
for f in sorted(os.listdir('app')):
    if not f.endswith('.py'): continue
    with open(f'app/{f}') as fh: content = fh.read()
    bp = re.search(r\"Blueprint\('(\w+)',.*url_prefix='(/api/\w+)'\)\", content)
    if not bp: continue
    prefix = bp.group(2)
    for m in re.finditer(r\"@\w+_bp\.route\('([^']+)',\", content):
        routes.add(prefix + m.group(1))
for r in sorted(routes): print(r)
"

# 2. 扫前端API调用
find frontend/src/views -name '*.vue' | while read f; do
  grep -n "api\.\(get\|post\|put\|delete\)" "$f"
done

# 3. 交叉验证 — 前端调用的每个API，后端是否有对应路由+方法
python3 -c "
import re, os
# 后端路由
backend = set()
for f in os.listdir('app'):
    ...
# 前端调用  
for root, dirs, files in os.walk('frontend/src/views'):
    for f in files:
        ...
        for a in re.finditer(r\"api\.(get|post|put|delete)\('/([^']+)'\", content):
            path = '/api/' + a.group(2)
            method = a.group(1).upper()
            if path not in backend: print(f'MISSING: {path}')
"
```

### 检查清单
1. ✅ 每个前端API调用都有对应的后端路由
2. ✅ HTTP方法匹配（GET/POST/PUT/DELETE）
3. ✅ 前端字段名匹配后端（如 `id_card` → `id_number`）
4. ✅ API返回数据格式与前端期望一致（数组 vs `{list,total}`）
5. ✅ 管理端所有前端功能都有对应管理端API

## 后端安全审计

### 认证检查
```bash
# 检查每个路由是否有认证装饰器
grep -n "\.route(" app/*.py | while read line; do
  file=$(echo $line | cut -d: -f1)
  line_num=$(echo $line | cut -d: -f2)
  route=$(echo $line | cut -d: -f3-)
  # 查看下3行是否有 @login_required / @admin_required
  sed -n "${line_num},$((line_num+3))p" "$file" | grep -q "@.*_required" || echo "⚠️ 无认证: $file:$route"
done
```

### bare except 检查
```bash
grep -rn "^[ \t]*except[ \t]*:" app/ --include="*.py"
# 修复: 全部改为 except Exception:
sed -i 's/^\([ \t]*\)except[ \t]*:/\1except Exception:/' app/*.py
```

### SQL注入检查
```bash
# f-string SQL — 检查是否拼接用户输入
grep -rn "execute(f[\"']" app/ --include="*.py"
# 安全标准: f-string 只拼接预检字段(ALLOWED白名单/固定order_map)，用户输入必须参数化
```

### 长函数检查
```bash
for f in app/*.py; do
  awk '/^def /{name=$2; lines=1; next} /^    /{lines++} /^[^ ]/{if(lines>60) print name"("lines"行) - "FILENAME; lines=0}' "$f"
done
```

## 优先修复顺序
1. 🔴 **无认证路由** — 审核/举报/管理类API必须有 `@admin_required`
2. 🟡 **bare except** — 吞真实错误，改为 `except Exception`
3. 🟢 **f-string SQL** — 低风险（预检字段），验证白名单后无需改
4. 🟢 **长函数** — 重构优先级低，代码质量优化

## 已验证的常见缺失
| 问题 | 本次发现 | 修复 |
|------|---------|------|
| `platform_review.py` 5个路由无认证 | 高危 | 全部加 `@admin_required` |
| `attendance.py` 3个路由无认证 | 中危 | 全部加 `@login_required` |
| 6个文件 bare except | 中危 | 改为 `except Exception` |
