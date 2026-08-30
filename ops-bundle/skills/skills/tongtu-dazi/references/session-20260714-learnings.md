# Session 2026-07-14 Learnings

## 1. Detail API 数据嵌套结构

**API 返回格式：**
```json
{"code": 0, "data": {"info": {"id": 23, "nickname": "小甜心", ...}}}
```

**陷阱：** axios 拦截器解包后得到 `{info: {...}}`，直接检查 `r.id` 永远为 `undefined`。

**修复模式：**
```javascript
const r = await api.get('/companion/detail?id=X')
const detail = r?.info || r  // 兼容两种格式
if (!detail || !detail.id) { safeToast('不存在') }
```

## 2. 底部操作栏 position:fixed 独立于父容器

**问题：** 微信浏览器中 `position: fixed` 在带背景/圆角/阴影的父级容器内定位异常。

**修复：** 将底部操作栏移到页面容器 `</div>` 之外，作为模板根级兄弟元素。

## 3. 微信支付服务器端确认（替代XHR回调）

**核心模式：** 支付成功后不依赖前端XHR回调，而是跳转到服务端确认端点，由服务器查询微信支付结果。

**端点：** `GET /api/pay/wxpay/confirm?order_no=xxx`

**流程：** 支付成功 → `location.href = '/api/pay/wxpay/confirm?order_no=X'` → 后端查微信 → 到账 → redirect 回充值页

## 4. JSAPI 接口安全域名

两个域名都必须添加：
- `dazi.openai2000.cn`（主站）
- `pay.openai2000.cn`（支付中转）

## 5. 信息服务套餐模式（合规改造）

将充值页改为套餐选择模式，不再显示单纯的金额输入：

```javascript
const packages = [
  { name: '单次匹配', price: 10, desc: '完成1次信息对接匹配' },
  { name: '5次套餐', price: 40, desc: '5次信息匹配对接，立省20%' },
  { name: '包月无限', price: 199, desc: '30天内无限次匹配对接', popular: true },
]
```
