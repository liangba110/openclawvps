# 后端安全审计清单（2026-07-06 全量审计发现）

## 1. @admin_required 覆盖率

必须逐路由检查。本期发现 5+ 处缺失：

| 文件 | 缺失的路由 | 风险等级 |
|------|-----------|---------|
| `platform_review.py` | `/verify/list`, `/verify/approve`, `/verify/reject`, `/reports`, `/report/handle` | 🔴 任何人都可审核/举报 |
| `admin.py` | `/withdrawals`, `/withdrawals/<id>/audit` | 🔴 任何登录用户可审核提现 |
| `coupon.py` | `/admin/list`, `/admin/create`, `/admin/usage/<id>` | 🟡 仅 @login_required |
| `agreement.py` | `/admin/list`, `/admin/save` | 🟡 仅 @login_required |

**检查命令：**
```bash
grep -n '@admin_bp\\|@login_required\\|def ' app/admin.py | grep -B1 'def ' | grep -v '@admin_required'
```

**修复：** 加 `@admin_required` 并从 `app.admin` 导入（不是 `app.utils`！）。

## 2. bare except: pass

所有 `except:` 必须改为 `except Exception:`，否则真实错误被静默吞噬。

```python
# ❌ 错误
except:
    pass

# ✅ 正确
except Exception:
    pass  # 或 log 或 toast
```

本期修复 6 个文件：`companion.py`, `customer_service.py`, `faq.py`, `platform_review.py`, `risk_control.py`, `token_auth.py`

## 3. f-string SQL 注入风险

使用 `execute(f"...{var}...")` 时，变量必须来自白名单或固定映射表。

| 文件 | 类型 | 风险评级 |
|------|------|---------|
| admin.py (12处) | `where_clause`/`order_by`/`set_clause` 来自 ALLOWED 白名单 | 🟢 低 |
| companion.py (5处) | `order_by` 来自固定 `order_map` | 🟢 低 |

**结论：** 当前所有 f-string SQL 使用的变量均来自白名单或固定字典，无直接用户输入注入风险。

## 4. 审核操作缺少 audit_log

**必须加 `audit_log()` 的审核操作：**

| 操作 | 文件 | 位置 |
|------|------|------|
| 陪玩师审核通过/拒绝 | `admin.py` | `playmate_audit()` |
| 实名认证通过/拒绝 | `admin.py` | `verify_approve()` / `verify_reject()` |
| 提现审核通过/拒绝 | `admin.py` | `withdrawal_audit()` |

```python
from app.audit_log import log as audit_log

audit_log(request.current_user['user_id'], 'review_playmate',
          target_type='companion', target_id=cid,
          detail={'action': action, 'status': status})
```

## 5. 变量作用域陷阱：conn 在 if 块内

**症状：** 某些请求正常，另一些返回 500（NameError）

**根因：** `conn` / `cur` 等数据库对象在 `if` 块内定义，后续代码块外引用：

```python
if 'phone' in data:
    conn = get_connection()  # ← 只在改手机时才定义
    ...

# 后续代码：
cur2 = conn.cursor()  # ← 不改手机时 conn 未定义 → NameError
```

**修复：** 在执行 SQL 前重新调用 `get_connection()`，不在 if 块内定义跨块使用的连接变量。

## 6. 未定义变量引用

| 文件 | 行 | 问题 | 修复 |
|------|-----|------|------|
| `user.py:568` | `register_by_code` | `cur.execute(..., (email,))` 使用未定义变量 `email`（应为 `phone`） | → `(phone,)` |
| `playmate_api.py:338` | `complete_order` | 同时用 `request.current_user` 和 `order_user` 更新两次 order_count | 删除错误的第一次更新 |

## 7. 多方法路由漏扫

正则 `/methods=\[([^\]]+)\]/` 只捕获列表的第一个方法，漏掉 `['GET', 'PUT']` 等多方法路由。

**修复扫描：**
```python
# 改用完整捕获
re.finditer(r"methods=\[([^\]]+)\]", content)
methods = [x.strip().strip("'\"") for x in m.group(1).split(',')]
```

本期发现 2 个漏扫：`/playmate/<int:cid>/audit` (PUT/POST), `/profile` (GET/PUT)
