# 支付站点回调映射表（2026-08-28 验证后状态）

## 统一支付网关（A 服务器 5005，pay.openai2000.cn）
- 微信回调 → 网关 `/api/v1/wxpay/notify`（公钥验签，certs/wx_public_key.pem）
- 网关按**订单号前缀**路由转发（`_notify_merchant`，网关格式 `{order_no, amount, status, timestamp}` + `X-Pay-Token: huizhiyun_gateway_2026`）

## 前缀 → 目的地路由
| 前缀 | 业务 | 回调目的地 | 状态 |
|---|---|---|---|
| TMP/SO/HY | 官网(www.openai2000.cn) | https://www.openai2000.cn/api/payment/notify | ✅ 已通（JSAPI+Native 双模式，自动回调）|

## 官网（www.openai2000.cn）回调细节（2026-08-28 验证）
- 代码：B 服务器 `/data/web/huizhiyunma/backend/routes/payment.js`（Express，8081 端口，nginx 反代）
- 订单号前缀：TMP=模板商城(pay_system_db.template_orders) / SO=套餐(huizhiyunma_db.package_orders) / HY=通用支付(huizhiyunma_db.payment_orders)
- 支付方式：JSAPI（微信内，oauth snsapi_base 拿 openid）+ Native（扫码，前端 QRCode 生成 dataURL）双模式，**都走统一网关**
- notify 鉴权：`X-Pay-Token: huizhiyun_gateway_2026` 头校验，`resolveOrder()` 按前缀路由到对应库表
- 落库差异：template_orders→status=1、package_orders→status=1、payment_orders→**status=2**（注意不是 1）
- 到账邮件通知：`sendNotify()`（mailer.js，SMTP）
- 前端轮询：`GET /api/payment/status/:orderNo`；下单前先 `wxpay/query` 查微信侧状态，SUCCESS 直接落库（防重复）
- 保留 `/api/payment/:orderNo/proof` 上传凭证接口作为管理员兜底（前端已不用）
- 注意：`www.openai2000.cn` curl 返回 301 是域名规范跳转（非错误），本机测试绕过 nginx 用 `http://127.0.0.1:8081`
| AE | AI电商站(ai.openai2000.cn) | https://ai.openai2000.cn/api/pay/notify | ✅ 双格式兼容已修 |
| SA | softapi(softapi.openai2000.cn) | https://softapi.openai2000.cn/api/recharge/callback | ✅ 已通 |
| SA2 | softapi多软件平台(softapi.openai2000.cn) | https://softapi.openai2000.cn/api/app/recharge/callback | ✅ 已通（2026-08-28 多软件平台新增） |
| CZ/JS/DMD/其他 | 同途搭子(dazi.openai2000.cn) | https://dazi.openai2000.cn/api/pay/notify/recharge | ✅ 已通（兜底分支） |

⚠️ **前缀匹配顺序**：网关 wx_notify 用 elif 顺序匹配，`SA2` 分支必须写在 `SA` 分支**之前**（`[:3]` 子前缀先于 `[:2]` 前缀），否则 SA2 订单被 SA 分支误吞。新增任何子前缀时先检查顺序。

## 下游 notify 双格式兼容代码（Next.js App Router 示例）
AI 电商站 `/data/disk/ai-ecom/app/api/pay/notify/route.ts` 的修复模式：

```ts
const GATEWAY_TOKEN = 'huizhiyun_gateway_2026';

// 模式1：网关转发 {order_no, amount, status} + X-Pay-Token
const gatewayOrderNo = payload.order_no as string;
const gatewayStatus = payload.status as number;
const gatewayToken = req.headers.get('X-Pay-Token') || '';
// 模式2：微信原生 {resource:{out_trade_no, trade_state, transaction_id}}
const resource = payload.resource as any;
const nativeOrderNo = resource?.out_trade_no;
const nativeTradeState = resource?.trade_state;

if (gatewayOrderNo && gatewayToken === GATEWAY_TOKEN && gatewayStatus === 1) {
  orderNo = gatewayOrderNo; transactionId = gatewayOrderNo; paid = true;
} else if (nativeOrderNo && nativeTradeState === 'SUCCESS') {
  orderNo = nativeOrderNo; transactionId = nativeTransactionId; paid = true;
}
```

要点：
- 网关格式**没有** `resource`、没有 `out_trade_no` → 只认原生格式的处理器会永远 404/空订单号
- 两种格式都要先 `getOrderByNo()` 查单，不存在返回 404
- 置 paid 后返回 `{code:'SUCCESS'}`

## Next.js standalone 站点改码流程（AI电商站）
```bash
# 1. 备份可回滚
sudo cp -r /data/disk/ai-ecom/.next /data/disk/ai-ecom/.next.bak_$(date +%Y%m%d_%H%M%S)
# 2. 改源码 /data/disk/ai-ecom/app/api/pay/notify/route.ts
# 3. 重新 build（Next.js standalone 改代码必须 rebuild，改 .ts 不生效）
cd /data/disk/ai-ecom && sudo -u aiecom env PATH=/home/ubuntu/.nvm/versions/node/v22.23.0/bin:$PATH npm run build
# 4. 重启（aiecom 用户自己的 pm2 daemon！）
sudo -u aiecom bash -c 'export PATH=/home/ubuntu/.nvm/versions/node/v22.23.0/bin:$PATH; export PM2_HOME=/home/aiecom/.pm2; pm2 restart ai-ecom-site'
# 5. 验证：curl notify 接口，两种格式各测一次（用不存在单号应返回 404 order not found = 格式解析通过）
```

## 陷阱记录
- 服务器上多个 pm2 daemon（ubuntu/aiecom/root 各一个）：必须用**对应用户**的 PM2_HOME，否则 `Permission denied on /home/ubuntu/.pm2/rpc.sock`
- AI电商站历史 62 单 paid 是**脚本/定时任务置的**（paid_at 整点 :02 秒），非自动回调——验证真实回调时别被假数据误导
- 同途搭子 recharge 表 status=0 的存量单：查微信侧 trade_state，NOTPAY/CLOSED 均为未支付，无需补单
