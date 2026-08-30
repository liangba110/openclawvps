# Admin Mirror Audit + Phone/Email Binding (2026-07-05 Session)

## Admin Mirroring Audit Pattern

When adding a new frontend feature, verify admin backend coverage:

```bash
# Step 1: list frontend routes
grep "path: '/" /opt/ttdazi/frontend/src/router/index.js | grep -v admin | grep -v ':pathMatch'
# Step 2: list admin routes  
grep "path: '/admin/" /opt/ttdazi/frontend/src/router/index.js
# Step 3: list admin backend APIs
grep "@admin_bp.route" /opt/ttdazi/backend/app/admin.py | grep -v "login"
# Step 4: check sidebar
grep 'push.*admin' /opt/ttdazi/frontend/src/views/admin/AdminSidebar.vue
```

## Phone/Email Binding — One-Time Irreversible

### DB
```sql
ALTER TABLE user ADD COLUMN phone_bound TINYINT DEFAULT 0;
```

### Admin Bind (`admin.py`)
```python
@admin_bp.route('/user/<int:uid>/bind-phone', methods=['POST'])
@admin_required
def bind_user_phone(uid):
    phone = request.get_json().get('phone', '').strip()
    # validate + check uniqueness + check phone_bound=0 → UPDATE SET phone=..., phone_bound=1
```

### User Self-Bind via `/api/user/update`
```python
# In update_profile(), BEFORE field processing:
if 'phone' in data:
    cur.execute("SELECT phone, phone_bound FROM user WHERE id=%s", (user_id,))
    u = cur.fetchone()
    if u and u['phone'] and u['phone_bound']:
        return fail('手机号已绑定，不可修改')
# When building SQL fields:
if 'phone' in data:
    fields.append('phone_bound=1')
```

### Frontend Convention
- `v-if="!user.phone_bound"` — show bind button + arrow  
- `v-if="user.phone_bound"` — show "已绑定" disabled
- `user.phone.includes('@')` — detect email-as-phone (unbound)

## Email Registration Fix
```python
# MUST save to email column:
cur.execute(
    "INSERT INTO user (username, phone, email, password, nickname, role, status) VALUES (%s,%s,%s,%s,%s,'user',1)",
    (email, email, email, hashed, nickname))
```
Backfill: `UPDATE user SET email=username WHERE email IS NULL AND username LIKE '%@%'`

## Login Query Must Include phone/phone_bound/email
```sql
SELECT id, username, password, nickname, ..., phone, email, phone_bound
FROM user WHERE phone=%s OR username=%s OR email=%s
```

## Verified AdminSidebar Menu Order
📊 仪表盘 → 👤 用户管理 → 🎮 陪玩师管理 → 📋 订单管理 → 🪪 实名审核 → 💰 财务明细 → 💬 客服消息 → 📨 消息记录 → 🤖 FAQ 学习 → ✏️ 代码编辑 → 🔒 安全监控 → ⚙️ 系统设置 → 🎟️ 优惠券管理 → 📜 协议管理 → 💳 提现审核 → 📝 内容管理 → ⭐ 评价管理
