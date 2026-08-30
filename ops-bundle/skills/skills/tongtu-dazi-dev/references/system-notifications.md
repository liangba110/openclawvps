# System Notification Events

## Verification Audit Notifications (in platform_review.py)

| Event | Recipient | icon | title | content |
|-------|-----------|------|-------|---------|
| Verify approved | User | ✅ | 实名认证通过 | 您的实名认证已通过，现在可以正常使用所有功能 |
| Verify rejected | User | ❌ | 实名认证未通过 | 您的实名认证未通过，原因：{reason}，请重新提交 |

**Implementation notes:**
- `verify_approve()` needs to get `user_id` from `verify_application` after update: `cur.execute("SELECT user_id FROM verify_application WHERE id=%s", (vid,))`
- `verify_reject()` needs the same: check `cur.rowcount` first before fetching
- Use `if 'uid' in locals() or 'uid' in dir():` guard since uid may not exist if no rows updated

## Companion Audit Notifications (in admin.py)

| Event | Recipient | icon | title | content |
|-------|-----------|------|-------|---------|
| Approved | Companion user | 🎉 | 陪玩师审核通过 | 您的陪玩师入驻申请已通过，您现在可以开始接单了！ |
| Rejected | Companion user | 📋 | 陪玩师审核未通过 | 您的陪玩师入驻申请未通过，请完善资料后重新提交 |

**Implementation notes:**
- After UPDATE companion SET status, query companion's user_id: `cur.execute("SELECT user_id, nickname FROM companion WHERE id=%s", (cid,))`
- Only send when `cur.rowcount > 0`

## Withdrawal Notifications

### User submits withdrawal (in playmate_api.py)

| Event | Recipient | icon | title | content |
|-------|-----------|------|-------|---------|
| Submit | User | 💰 | 提现申请已提交 | 提现¥{amount:.2f}申请已提交，等待管理员审核 |

**Implementation notes:**
- `uid = request.current_user['user_id']` — available via `companion_required` decorator's `login_required`

### Admin audits withdrawal (in admin.py)

| Event | Recipient | icon | title | content |
|-------|-----------|------|-------|---------|
| Approved | Companion user | ✅ | 提现审核通过 | 您的提现¥{amount:.2f}申请已通过，请查收 |
| Rejected | Companion user | ❌ | 提现审核未通过 | 您的提现¥{amount:.2f}申请未通过 |

**Implementation notes:**
- After UPDATE withdraw SET status, query withdrawal's companion_id: `cur.execute("SELECT companion_id, amount FROM withdraw WHERE id=%s", (wid,))`
- Then query companion's user_id: `cur.execute("SELECT user_id FROM companion WHERE id=%s", (...))`
- `amount` needs `float()` conversion for display

## Full Notification Event Map

### Order events (in order.py + payment.py)
See `references/message-notification-system.md`

### System events (in platform_review.py, admin.py, playmate_api.py)

| Event | Stored in | Recipient | type | icon | title |
|-------|-----------|-----------|------|------|-------|
| Order created | order.py | Companion | order | 📋 | 新待付订单 |
| Order created | order.py | User | order | 📝 | 订单已创建 |
| Payment success | order.py | User | order | 💚 | 支付成功 |
| User confirms | order.py | Companion | order | ▶️ | 服务已开始 |
| Companion completes | order.py | User | order | ✅ | 订单已完成 |
| Verify approved | platform_review.py | User | system | ✅ | 实名认证通过 |
| Verify rejected | platform_review.py | User | system | ❌ | 实名认证未通过 |
| Companion approved | admin.py | User | system | 🎉 | 陪玩师审核通过 |
| Companion rejected | admin.py | User | system | 📋 | 陪玩师审核未通过 |
| Withdrawal submitted | playmate_api.py | User | system | 💰 | 提现申请已提交 |
| Withdrawal approved | admin.py | User | system | ✅ | 提现审核通过 |
| Withdrawal rejected | admin.py | User | system | ❌ | 提现审核未通过 |
