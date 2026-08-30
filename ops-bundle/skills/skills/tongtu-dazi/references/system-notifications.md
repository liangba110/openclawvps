# 系统通知事件清单（非订单类）

## 实名认证审核

| 事件 | 文件 | 函数 | 通知接收方 | icon | title |
|------|------|------|-----------|------|-------|
| 审核通过 | `platform_review.py` | `verify_approve()` | 申请用户 | ✅ | 实名认证通过 |
| 审核拒绝 | `platform_review.py` | `verify_reject()` | 申请用户 | ❌ | 实名认证未通过 |

### verify_approve 实现要点

```python
# 已有 uid 变量（在 cur.execute("SELECT user_id FROM verify_application WHERE id=%s", (vid,)) 中获取）
send_notification(uid, '您的实名认证已通过，现在可以正常使用所有功能',
    ntype='system', title='实名认证通过', icon='✅')
```

### verify_reject 实现要点（⚠️ 缺少 uid 变量）

```python
cur.execute("UPDATE verify_application SET status=2, reject_reason=%s WHERE id=%s AND status=0", (reason, vid))
if cur.rowcount:
    cur.execute("SELECT user_id FROM verify_application WHERE id=%s", (vid,))
    uid = cur.fetchone()['user_id']  # ← 需要手动查询！
conn.commit()
if 'uid' in dir():  # 或使用局部变量 flag
    send_notification(uid, f'您的实名认证未通过，原因：{reason}，请重新提交',
        ntype='system', title='实名认证未通过', icon='❌')
```

**⚠️ verify_reject 没有自动获取 uid！** approve 函数有 `uid = cur.fetchone()['user_id']`，但 reject 没有。需要加上同样的查询逻辑。

## 陪玩师入驻审核

| 事件 | 文件 | 函数 | 通知接收方 | icon | title |
|------|------|------|-----------|------|-------|
| 审核通过 | `admin.py` | `playmate_audit()` | 申请用户 | 🎉 | 陪玩师审核通过 |
| 审核拒绝 | `admin.py` | `playmate_audit()` | 申请用户 | 📋 | 陪玩师审核未通过 |

```python
# 在审核函数内，auth 通过后需要先查询 companion 的 user_id
cur.execute("SELECT user_id, nickname FROM `companion` WHERE id=%s", (cid,))
c = cur.fetchone()
if c:
    if status == 1:
        send_notification(c['user_id'], '您的陪玩师入驻申请已通过，您现在可以开始接单了！',
            ntype='system', title='陪玩师审核通过', icon='🎉')
    else:
        send_notification(c['user_id'], '您的陪玩师入驻申请未通过，请完善资料后重新提交',
            ntype='system', title='陪玩师审核未通过', icon='📋')
```

## 提现流程

| 事件 | 文件 | 函数 | 通知接收方 | icon | title |
|------|------|------|-----------|------|-------|
| 提现申请提交 | `playmate_api.py` | `withdraw()` | 申请用户 | 💰 | 提现申请已提交 |
| 提现审核通过 | `admin.py` | `withdrawal_audit()` | 申请用户 | ✅ | 提现审核通过 |
| 提现审核拒绝 | `admin.py` | `withdrawal_audit()` | 申请用户 | ❌ | 提现审核未通过 |

### withdraw() — 获取 uid

```python
# companion_required 提供了 request.companion_id 和 request.current_user
# 但要通知当前用户，直接用 request.current_user['user_id']
uid = request.current_user['user_id']
send_notification(uid, f'提现¥{amount:.2f}申请已提交，等待管理员审核',
    ntype='system', title='提现申请已提交', icon='💰', data_id=0)
```

### withdrawal_audit() — 获取 uid（需 JOIN 链）

```python
cur.execute("UPDATE `withdraw` SET status=%s WHERE id=%s", (status, wid))
if cur.rowcount:
    cur.execute("SELECT companion_id, amount FROM `withdraw` WHERE id=%s", (wid,))
    w = cur.fetchone()
    if w:
        cur.execute("SELECT user_id FROM `companion` WHERE id=%s", (w['companion_id'],))
        u = cur.fetchone()
        if u:
            send_notification(u['user_id'], f'您的提现¥{float(w["amount"]):.2f}申请已通过，请查收',
                ntype='system', title='提现审核通过', icon='✅')
```

**⚠️ 提现审核需要两层 JOIN：withdraw → companion → user**，因为 `withdraw` 表存的是 `companion_id`，不是 `user_id`。

## 三大通知点——uid 获取方式对比

| 场景 | uid 来源 | 注意事项 |
|------|---------|---------|
| 实名认证 approve | `verify_application` 表查询 | 已有现成代码 |
| 实名认证 reject | `verify_application` 表查询 | **需要自己加查询！** 原代码遗漏 |
| 陪玩师审核 | `companion` 表查询 | 用审核目标 `cid` 查询 |
| 提现申请 | `request.current_user['user_id']` | 用户主动操作，当前用户就是接收方 |
| 提现审核 | `withdraw.companion_id → companion.user_id` | 两层 JOIN 链 |

## import 要求

```python
from app.utils import send_notification
```

- `platform_review.py` 原本没有 import `send_notification`，需要添加
- `playmate_api.py` 原本没有 import `send_notification`，需要添加
- `admin.py` 已有（从 `app.utils` import），无需添加
- `order.py` / `payment.py` 已有
