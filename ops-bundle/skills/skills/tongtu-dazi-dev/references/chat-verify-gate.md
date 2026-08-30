# 实名认证聊天拦截（verify_status 门禁）

## 业务规则（用户确认，2026-07-31）
**发起聊天（私聊/客服对话）前必须完成实名认证。** 拦截标准：`user.verify_status == 1`（管理员审核通过）才算完成。

## verify_status 状态语义
| 值 | 含义 | 发消息结果 |
|:---|:-----|:-----------|
| 0 | 未认证 | `403 请先完成实名认证后再发起聊天` |
| 1 | 已通过（管理员审核通过） | ✅ 正常发送 |
| 2 | 待审核（用户已提交，等管理员） | `403 实名认证审核中，审核通过后才能发起聊天` |
| 3 | 被拒绝（verify_reason 记录原因） | `403 实名认证未通过，请重新提交认证` |

提交认证后用户表直接置 `verify_status=2`（待审核），管理员在后台 AdminVerify 通过后置 1、拒绝置 3。

## 后端硬拦截（核心防线，防绕过）
`/opt/ttdazi/backend/app/chat.py` 的 `/api/chat/send`（POST，login_required）：
在插入 `chat_message` 前查 `SELECT verify_status FROM user WHERE id=user_id`，非 1 则 `return fail(msg, code=403)`（utils.fail 支持 code 参数，返回 `{"code":403,...}`）。

## 前端拦截（体验层，两个聊天页都要改）
- `views/CustomerService.vue`（详情页"💬聊一聊/免费聊天" → /service 的主聊天页）
- `views/ChatConversation.vue`（私聊页 /chat）

统一模式：
```js
// verify_status 1=已通过 2=审核中 3=被拒 0/undefined=未认证
function checkVerify() {
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  const vs = user.verify_status
  if (vs === 1 || user.verified) return { ok: true }
  if (vs === 2) return { ok: false, msg: '实名认证审核中，审核通过后才能发起聊天' }
  if (vs === 3) return { ok: false, msg: '实名认证未通过，请重新提交认证' }
  return { ok: false, msg: '请先完成实名认证后再发起聊天' }
}
// 未通过：Toast 提示 → 800ms 后 router.push('/verify-identity')
```
注意：localStorage 的 user 是登录时的快照，管理员审核通过后用户需重新登录/刷新 profile 才能拿到 verify_status=1；
后端硬拦截兜底，所以前端判断过时只是体验问题不是安全问题。

## 实名认证页
`/verify-identity`（views/VerifyIdentity.vue）：隐私协议弹窗 → 上传身份证正反面（OCR 自动识别姓名/身份证号）→ 提交 `/user/verify` → 管理员后台审核。
已认证判断：`user.verify_status == 1 || 2 || user.verified`（注意前端页面本身把 2 也当"已认证"显示，与聊天拦截的严格标准不同）。

## 验证方法
```bash
# 已认证用户(verify_status=1)发送 → 成功
# 未认证用户(verify_status=0)发送 → {"code":403,"msg":"请先完成实名认证后再发起聊天"}
curl -X POST http://127.0.0.1:5002/api/chat/send -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' -d '{"to_id":10047,"content":"test"}'
# 查消息是否入库：SELECT * FROM chat_message WHERE content='test';
```
