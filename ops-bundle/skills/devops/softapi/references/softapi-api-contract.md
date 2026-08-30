# softapi 软件侧 API 契约（对接用）

基础地址：`https://softapi.openai2000.cn`（全部 HTTPS，JSON）
完整文档：`/opt/software_auth/docs/对接文档.md`（发给开发者的正式版，含 Python/Node 签名示例）

## 签名算法
```
sign = md5(app_id + 排序参数拼接 + app_key + timestamp)
排序参数：除 sign/timestamp 外的所有参数，按键名 ASCII 升序，拼 key1value1key2value2...
timestamp 与服务器差 >300s 失效
```

## 接口一览
| 方法/路径 | 签名 | 说明 |
|---|---|---|
| POST /api/app/register | 否 | {app_name, notify_url?, logo_url?} → {app_id, app_key} |
| GET /api/app/info | 否 | ?app_id= → 软件名/logo |
| POST /api/app/user/register | 是 | {app_id, username, password} → {user_id} |
| POST /api/app/user/login | 是 | → {token, user_id, username, vip_type, vip_expire_time} |
| GET /api/app/user/auth | 否 | ?app_id=&token= → 权限校验（403=过期）|
| POST /api/app/recharge/create | 是 | {app_id, token, goods_type} → {order_sn, amount, pay_url} |
| GET /api/app/recharge/query | 否 | ?app_id=&token=&order_sn= → 订单状态 |
| GET /api/app/recharge/list | 否 | ?app_id=&token= → 订单列表 |
| POST /api/app/recharge/callback | 网关Token | 内部，网关转发用（X-Pay-Token: huizhiyun_gateway_2026）|
| POST /api/app/page/login|register|recharge/create | 否 | 收银台专用免签名 |

## 套餐（全局默认；每软件可在管理后台改 price_1~4）
| goods_type | 套餐 | 默认价 | 时长 |
|---|---|---|---|
| 1 | 日卡 | 9.9 | 1天 |
| 2 | 月卡 | 29.9 | 30天 |
| 3 | 年卡 | 199.9 | 365天 |
| 4 | 永久 | 520.0 | 永久（vip_expire_time=NULL）|

## 下单响应 pay_url
`weixin://wxpay/bizpayurl?pr=xxx` —— **直接用此字符串生成二维码，勿替换 weixin:// 前缀**（曾经替换成 https 导致扫码报错）。

## 软件回调（支付成功转发到软件 notify_url）
POST JSON：
```json
{"app_id":"APP...","order_sn":"SA2...","amount":29.9,"goods_type":2,
 "user_id":1,"status":1,"timestamp":"1787923205","sign":"..."}
```
验签：`md5(app_id + amount{amount} + goods_type{goods_type} + order_sn{order_sn} + status{status} + timestamp{ts} + user_id{user_id} + app_key + ts)`
接收方：返回 HTTP 200 即成功；失败会重试（间隔递增，最长 24h）；按 order_sn 判重（幂等）。

## 错误码
200 成功 / 400 参数业务错误 / 401 未登录或软件无效 / 403 签名无效或封禁或权限过期 / 404 不存在 / 500 服务异常

## 注意事项
- app_key 只在软件服务端，绝不下发客户端
- 签名 5 分钟时效
- 订单号前缀 SA2 是平台路由标识，勿改
- 未支付订单 30 分钟失效需重下单
- 每软件用户体系独立（A 软件用户不能登 B 软件）
