---
name: wechat-pay-callback-troubleshooting
description: 微信支付回调不通的系统性排障。触发词：支付成功但没到账、回调收不到、扫码支付无反应、notify 不生效、订单 status=0。
version: 1.0.0
author: hermes
license: MIT
platforms: [linux]
---

# 微信支付回调不通 · 系统性排障

## 触发条件
- 微信扫码支付成功，但业务系统（订单/VIP/余额）未更新
- 支付回调（notify）收不到 / 不生效
- 历史订单全部 status=0

## 全站点回调链路图（2026-08 已全部自动回调）
| 站点 | 订单前缀 | 网关路由 | 回调端点 |
|---|---|---|---|
| 同途搭子 | CZ/JS/DMD | 兜底→dazi | dazi.openai2000.cn/api/pay/notify/recharge |
| softapi | SA | SA分支 | softapi.openai2000.cn/api/recharge/callback |
| softapi多软件平台 | SA2 | SA2分支 | softapi.openai2000.cn/api/app/recharge/callback |
| AI电商站 | AE | AE分支 | ai.openai2000.cn/api/pay/notify（兼容双格式）|
| 官网 | TMP/SO/HY | TMP/SO/HY分支 | www.openai2000.cn/api/payment/notify（JSAPI+Native）|

网关文件：/opt/ttdazi/payment_service/api.py（wx_notify 前缀路由 + _notify_merchant 转发，X-Pay-Token: huizhiyun_gateway_2026）

## 陷阱：前缀路由顺序（子前缀必须先匹配）
Python `elif` 按顺序匹配：`out_trade_no[:2] in ('SA',)` 会**先吃掉** `SA2...` 订单！新增子前缀（如 SA2）时，`elif out_trade_no[:3] in ('SA2',)` **必须放在** `elif out_trade_no[:2] in ('SA',)` **之前**，否则 SA2 订单被误路由到旧回调端点，业务侧永远收不到。检查任何前缀路由修改时先看顺序。

## 关键背景知识（2024+ 新规）
1. **微信已停发「平台证书」，全面切「微信支付公钥」模式**（APIv3 新商户默认）
   - 商户平台 → API安全 → 微信支付公钥 → 下载 `pub_key.pem`（`-----BEGIN PUBLIC KEY-----` 开头）
   - 回调签名头 `Wechatpay-Serial` 以 `PUB_KEY_ID_` 开头 → 用公钥验签
   - 旧代码用 `wx_platform_cert.pem` 验签会**永远失败**（且该文件可能存的是下载失败的错误 JSON）
2. **APIv3 密钥必须与商户平台一致**（重置后需同步服务器代码）
3. **Native 回调链接**（商户平台产品中心→开发配置）配完整 URL：`https://pay.openai2000.cn/api/v1/wxpay/notify`
4. 微信回调服务器 IP 段：`121.51.x.x`、`220.196.x.x`、`101.226.x.x`、`140.207.x.x`、`163.177.x.x`（121.51 最容易被漏判）

## 排障顺序（从快到慢）

### ① 确认支付是否真的成功（微信侧）
```bash
curl -s "http://127.0.0.1:5005/api/v1/wxpay/query?out_trade_no=<单号>" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('trade_state'))"
# SUCCESS=微信侧已收钱; NOTPAY=没支付成功(可能付了别的单,逐个查最近订单)
```

### ② 确认回调是否到达服务器（抓包，注意正确解析）
```bash
sudo timeout 60 tcpdump -i any -nn 'tcp port 443' > /tmp/tcp.log 2>/dev/null
# 正确解析入站(目标本机443):
# tcpdump 格式: "时间 网卡 In  IP 源IP.端口 > 目标IP:端口"（双空格 In  IP！）
# ⚠️ 关键陷阱：用 awk '{print $3}' 取到的是网卡名不是IP！
# 正确提取方式（grep -o 最可靠）：
grep -o 'In  IP [0-9.]*\.[0-9]* > <本机IP>:443' /tmp/tcp.log | awk '{print $3}' | sed 's/\.[0-9]*$//' | sort | uniq -c
# 或更通用（按目标端口443过滤）：
grep -o 'In  IP [0-9.]*\.[0-9]*' /tmp/tcp.log | awk '{print $3}' | sed 's/\.[0-9]*$//' | sort | uniq -c | sort -rn | head -10
# 微信回调特征: 121.51.x.x 等腾讯IP → 本机443, 有ClientHello(268B)+加密回调(1705B)
```

### ③ 若回调到达但业务未更新 → 验签问题（最常见根因）
```bash
# 网关 wxpay.py 的 verify_notify 逻辑
# 新写法: 公钥优先(serial 以 PUB_KEY_ID_ 开头用 wx_public_key.pem), 回退平台证书
# 检查 wx_platform_cert.pem 内容: 如果是 {"code":"SIGN_ERROR"...} 说明是错误响应不是证书!
head -1 /opt/ttdazi/payment_service/certs/wx_platform_cert.pem
# 正确证书以 "-----BEGIN CERTIFICATE-----" 开头
```

### ④ 验签密钥一致性
- 服务器 `WX_API_KEY_V3` == 商户平台 APIv3密钥（重置后必须同步代码+重启网关）

### ⑤ 证书/网络层（较少见但遇过）
- **Caddy 证书 ECDSA 微信不认**：pay 域名必须 RSA 证书
  - Caddy `key_type rsa` 不支持！需 certbot 签 RSA + Caddy `tls /path/fullchain.pem /path/privkey.pem` 手动指定
  - certbot 签 RSA: `certbot certonly --webroot -w /var/www/certbot -d pay.xxx.cn --key-type rsa --rsa-key-size 2048`
  - 需要 Caddyfile 加 `http://pay.xxx.cn { root * /var/www/certbot; file_server }` 处理 ACME challenge
  - 证书复制到 Caddy 可读目录(/var/lib/caddy/certs/) + 续期钩子同步
- **腾讯云安全组**可能挡 80 端口(LE 验证)但 443 通: 用 TLS 或 DNS 验证绕开
- **云镜 YJ-FIREWALL-INPUT** 可能拦截 LE 验证 IP: 临时摘除 `iptables -D INPUT 1`, 签完恢复
- LE 速率限制: 1h 内 5 次失败会锁, 等窗口或换验证方式

## 修复清单（公钥模式迁移）
1. 商户平台下载公钥 → 存 `certs/wx_public_key.pem`
2. `verify_notify` 改公钥优先:
```python
pubkey_file = f'{CERT_DIR}/wx_public_key.pem'
if serial.startswith('PUB_KEY_ID_') and os.path.exists(pubkey_file):
    public_key = serialization.load_pem_public_key(open(pubkey_file,'rb').read(), default_backend())
# 否则回退平台证书
```
3. 同步 APIv3 密钥 + 重启网关
4. 微信回调重试机制会**自动补发**历史订单(最长24h), 修好后旧单自动到账

## 下游站点回调格式兼容（多站走统一网关时必查）
统一网关转发给业务站的回调是**网关格式** `{order_no, amount, status, timestamp}` + `X-Pay-Token: huizhiyun_gateway_2026` 头；
微信**原生回调**是 `{resource:{out_trade_no, trade_state, transaction_id}}`。**两者完全不同**！

- 业务站 notify 只认微信原生格式 → 收网关转发必失败（AI电商站踩过：解析 `out_trade_no` 永远为空）
- 修复：notify 处理器**同时兼容两种格式**（有 X-Pay-Token 头走网关分支，有 resource 走原生分支）
- 完整双格式代码 + 各站点回调映射表见 `references/payment-sites-callback-map.md`

## 陷阱
- tcpdump 解析字段错误导致误判"回调没来"（实际来了）
- 商户平台回调链接只填域名/根路径可能无效，要完整 URL
- 测试时用户可能付的是另一笔单，逐个查最近订单微信侧状态
- **Next.js standalone 站点（如 AI电商站 /data/disk/ai-ecom）改 notify 源码后必须 `npm run build` + pm2 restart**，改 .ts 不会自动生效
- pm2 多用户共存：aiecom 站要用 `sudo -u aiecom env PM2_HOME=/home/aiecom/.pm2 pm2 restart`，用 ubuntu 的 pm2 会报 Permission denied (rpc.sock)
- 改支付/回调代码前先备份当前 `.next` 目录（`cp -r .next .next.bak_时间戳`），build 失败可秒回滚

## 验证
- 全站回归 200
- 重新下一笔 1 元测试单扫码支付 → 业务侧订单 status=1
- 查业务日志: "充值成功" 关键字
- 多站场景：逐个站点验证回调（同途搭子 recharge表/softapi recharge_order/AI电商 site.db orders/官网 payment_orders）
- **2026-08-28 起四大支付站点已全部微信自动回调**：同途搭子(CZ/JS/DMD)、softapi(SA)、AI电商站(AE)、官网(TMP/SO/HY)——不要再按"人工补单"假设处理，回调不通一律按本 skill 排障

## 状态快照（2026-08-28 修复后）
- 网关 verify_notify：公钥优先 + 平台证书回退 ✅
- APIv3 密钥：`qAby5W4Tj7dLUuq9HUQNiZxhpvUtCXv8`（商户平台已同步）✅
- pay.openai2000.cn 证书：RSA 2048（/var/lib/caddy/certs，Caddy 手动 tls）✅
- 微信支付公钥：certs/wx_public_key.pem ✅
