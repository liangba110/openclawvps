# Admin Bind-Phone — One-Time Phone Binding

## Feature

Admin can bind a phone number for any user. Once bound, it cannot be modified.

## DB

```sql
ALTER TABLE user ADD COLUMN phone_bound TINYINT NOT NULL DEFAULT 0 COMMENT '手机号是否已绑定不可修改';
```

## Backend API: `POST /api/admin/user/<uid>/bind-phone`

**Body:** `{"phone": "13800138000"}`

**Logic:**
1. Validate 11-digit phone number
2. Check phone uniqueness: `SELECT id FROM user WHERE phone=%s AND id!=%s`
3. Check user exists and not already bound: `SELECT phone, phone_bound FROM user WHERE id=%s`
4. Reject if `phone_bound == 1`: "该用户手机号已绑定，不可修改"
5. `UPDATE user SET phone=%s, phone_bound=1 WHERE id=%s`

**Response:** `{"code": 0, "data": null, "msg": "绑定成功"}`

## Frontend (AdminUsers.vue)

**User card actions area:**
```html
<div class="u-actions">
  <button v-if="!u.phone_bound" class="btn-phone" @click="openBindPhone(u)">绑手机</button>
  <button v-if="u.phone_bound" class="btn-bound" disabled>已绑定</button>
  <button class="btn-toggle" v-if="u.role !== 'companion'" @click="toggleCompanion(u)">升陪玩师</button>
</div>
```

**Bind dialog:**
```html
<div v-if="bindShow" class="modal-overlay" @click.self="bindShow = false">
  <div class="modal-box">
    <div class="modal-title">绑定手机号</div>
    <p class="modal-desc">为 <strong>{{ bindTarget?.nickname }}</strong> 绑定手机号，绑定后用户不可修改</p>
    <input class="modal-input" v-model="bindPhone" placeholder="输入11位手机号" maxlength="11" @keyup.enter="doBindPhone" />
    <div class="modal-actions">
      <button class="modal-btn cancel" @click="bindShow = false">取消</button>
      <button class="modal-btn confirm" @click="doBindPhone" :disabled="bindLoading">确认绑定</button>
    </div>
  </div>
</div>
```

**Script:**
```js
const bindShow = ref(false)
const bindTarget = ref(null)
const bindPhone = ref('')
const bindLoading = ref(false)

function openBindPhone(u) {
  bindTarget.value = u
  bindPhone.value = ''
  bindShow.value = true
}

async function doBindPhone() {
  if (!bindPhone.value || bindPhone.value.length !== 11) { showToast('请输入11位手机号'); return }
  bindLoading.value = true
  try {
    await api.post(`/admin/user/${bindTarget.value.id}/bind-phone`, { phone: bindPhone.value })
    showToast('绑定成功')
    bindShow.value = false
    load()
  } catch(e) { showToast(e.message || '绑定失败') }
  finally { bindLoading.value = false }
}
```

## Admin Users Query — Must Include `phone_bound`

```python
SELECT id, phone, phone_bound, email, username, nickname, avatar, gender, city, ...
FROM user WHERE ...
```
