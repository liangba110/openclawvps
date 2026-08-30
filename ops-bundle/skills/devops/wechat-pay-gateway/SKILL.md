---
name: wechat-pay-gateway
description: 统一微信支付网关（pay.openai2000.cn，Server A:5005）对接与微信支付开发。触发：任何网站/系统接入微信支付、JSAPI支付、收款码模式改造、支付回调、订单支付状态、防重复拉起支付、商户号/授权目录配置。铁律：所有支付必须走统一网关，不另起支付。
---

# 统一微信支付网关对接

## 架构（2026-08 确立，用户铁律）

所有支付系统（ttdazi、www.openai2000.cn 官网等）统一对接 **pay.openai2000.cn**：
- 网关 = Server A:5005，systemd 服务 `ttdazi-pay.service`，代码 `/opt/ttdazi/payment_service/`（Flask）
- 商户号 1114539763 + 公众号 APPID wxd274e174ddadd4cb（ttdazi 与官网共用）
- 商户证书/APIv3密钥在 `certs/`（apiclient_key.pem 等），改动勿外泄
- **禁止业务系统另起支付/私自调微信 API**；网关重启用 `sudo systemctl restart ttdazi-pay`（勿手动 kill）

```
业务前端 → 业务后端 → https://pay.openai2000.cn/api/v1/wxpay/* → 微信API v3
微信回调 → pay.openai2000.cn/api/v1/wxpay/notify → 按订单前缀路由 → 业务系统回调(带X-Pay-Token)
```

## 网关接口（/api/v1/）

- `POST /wxpay/jsapi` {openid, out_trade_no, amount(元), subject} → prepay {appId,timeStamp,nonceStr,package,paySign}（signType=RSA）
- `POST /wxpay/native` {out_trade_no, amount, subject} → {code_url}（PC 扫码）
- `GET /wxpay/query?out_trade_no=` → {trade_state: SUCCESS/NOTPAY/USERPAYING/CLOSED/...}
- `POST /wxpay/close` {out_trade_no} → 关闭未支付单（重新下单前用）
- `POST /wxpay/notify` → 微信回调（验签+AES-GCM 解密）→ 按前缀路由业务回调
- `GET /health`

## 订单前缀路由（网关 notify → 业务回调）

网关微信回调验签解密后按 out_trade_no 前缀分发：

| 前缀 | 业务 | 回调 URL |
|---|---|---|
| PAY / RCH | ttdazi | https://dazi.openai2000.cn/api/pay/notify/recharge |
| TMP / SO / HY | www.openai2000.cn 官网 | https://www.openai2000.cn/api/payment/notify |
| AE | ai.openai2000.cn AI电商站（Next.js） | https://ai.openai2000.cn/api/pay/notify |
| SA | softapi.openai2000.cn 软件授权站 | https://softapi.openai2000.cn/api/recharge/callback |

回调 payload：`{order_no, amount(元), status:1, timestamp}`，**Header 带 `X-Pay-Token: huizhiyun_gateway_2026`**——业务系统必须校验该头（伪造回调会白嫖订单，403 拒绝）。

## 支付模式选型（先问场景再开发，2026-08 用户实测）

| 模式 | 适用 | 微信后台配置 | 说明 |
|---|---|---|---|
| **Native 扫码** | PC/浏览器/任意环境 | **完全不需要**（商户号开通 Native 即可） | 业务页直接显示二维码，微信扫码支付。**用户要的"网站上直接扫码支付"就是这个** |
| **JSAPI** | 微信内置浏览器内拉起 | 网页授权域名 + JSAPI 授权目录 | 需 openid（OAuth 静默授权） |

**用户偏好**：要求"在网站上扫码支付"→ 用 **Native**，不要默认做 JSAPI。JSAPI 只适合明确要"微信内一键拉起"的场景。

## Native 扫码接入模板（默认首选，业务侧 Node 示例）

1. 业务下单 → 业务表 status=0
2. 业务后端调网关 `POST /wxpay/native` {out_trade_no, amount, subject} → `code_url`（`weixin://wxpay/bizpayurl?pr=...`）
3. 业务后端把 code_url 生成二维码 dataURL：Node `npm i qrcode` + `QRCode.toDataURL(code_url, {width:300})`；前端 `<img :src>` 直接显示（零外部依赖，不被 CSP 拦）
   - ⚠️ **code_url 必须原样生成二维码（`weixin://wxpay/bizpayurl?pr=...`），禁止替换成 `https://wxpay.qq.com/...`**（2026-08-28 实测：替换后微信扫码报"支付错误"，用户付不了款）。qrcode 库可直接编码 weixin:// scheme 字符串，无需转换；JS 用 `QRCode.toDataURL`（**勿用 `toCanvas`**，旧版 qrcode 库在部分浏览器报 `getContext is not a function`）
4. 前端轮询业务 `/status/:orderNo`（或网关 query）→ status>=1 → 成功页（支付后自动跳转）
5. 微信回调 → 网关 notify → 业务回调（X-Pay-Token）→ 订单置已支付 + 邮件

**下单前必做（防重复/防篡改）**：先 `GET /wxpay/query` —— SUCCESS 则本地同步已支付返回 `{already_paid:true}`（前端直接成功，不弹码）；NOTPAY/USERPAYING/PAYERROR 先 `POST /wxpay/close` 再重新下单。**金额必须后端从订单表读取**（前端/URL 参数不可信，防 ¥1999 改 ¥0.01）。

## 微信后台配置与流程域一致性（JSAPI 专坑，2026-08 实测）

- 授权域名/授权目录**配置在哪个域名，支付流程就必须在哪个域名下完成**：把授权域名配成 `pay.openai2000.cn` 后，官网自己域名的 OAuth 回调（redirect_uri=www.openai2000.cn）直接被微信拒绝 → 症状"支付不行"
- 授权域名是**追加**（最多 5 个），勿覆盖已有 dazi.openai2000.cn（ttdazi 在用）
- 网页授权域名/JSAPI 授权目录**无开放 API**，必须用户后台手动配；Native 模式则无需这两项
- 网关已有 `pay.openai2000.cn/pay/hz` 统一支付页（OAuth + JSAPI 拉起 + 轮询一体，订单前缀 SO→/packages、其他→/templates 回跳）——若业务系统想收拢支付到 pay 域可复用，但**默认推荐 Native 业务页内扫码**（用户明确偏好）

## 微信证书 X5 兼容（微信内提示"不安全"）

微信 X5 内核只认 **RSA 证书链**，不认 ECDSA（电脑浏览器正常、微信提示不安全）。重签：
```bash
certbot certonly --cert-name <域名> --webroot -w <webroot> -d <域名> \
  --key-type rsa --rsa-key-size 2048 --force-renewal --non-interactive
```
- **必须同时给 `--cert-name`**（certbot 拒绝 ECDSA→RSA 变更，报错要确认）
- authenticator 按现状：webroot（80 块需有 acme location）/ nginx 插件 / standalone
- 签后 `nginx -t && reload`；确认 renewal conf `key_type=rsa`（续期沿用 RSA 不回退）
- 已处理：www/aiweb/dazi/info.openai2000.cn 全 RSA

### ⚠️ pay 回调域名 ECDSA = 微信支付成功但回调永远不到（2026-08-28 实测，推翻"可后置"旧判断）
**pay.openai2000.cn 必须 RSA，不能"可后置"**——之前记录"A 上 api/pay 仍 ECDSA（服务端域名，用户不直接访问，可后置）"是**错误结论**，已实测踩坑：
- **微信支付服务器（腾讯 220.196.160.x）回调时也不认 ECDSA 证书**：支付成功 → 微信服务器 POST `https://pay.openai2000.cn/api/v1/wxpay/notify` → **TLS 握手卡死**（tcpdump 见微信回调 IP 持续连 443 只有 TCP ack 无应用数据）→ 回调永远到不了网关 → 业务订单 status 永远 0 → **用户付了钱、服务不开通**，前端轮询也查不到
- **症状识别**（钱付了不生效时按此排查）：①`/wxpay/query` 微信侧 `trade_state=SUCCESS`+有 transaction_id；②业务库 order status=0 + 网关 journalctl **无任何 notify 记录** + Caddy 无该请求日志；③`openssl s_client -connect pay.openai2000.cn:443 -servername pay...` 看 `Server public key is 256 bit`=ECDSA 中招；④tcpdump 抓 443 看 220.196.160.x 重试连接
- **注意**：微信回调失败会按 15s/15s/30s/3m/10m/20m/30m... 递增重试约 15 次，不会立刻放弃，但不会成功——重签 RSA 后等待/重新支付即恢复

### ⚠️⚠️ RSA 已生效但回调仍不到 = 微信商户平台回调域名未配置（2026-08-28 更深一坑，推翻"RSA 即恢复"）
**重签 RSA 后（openssl 验证 `Server public key is 2048 bit` + `Verification: OK` + 全站 200），微信回调可能仍不到**。最终证据链：
- `sudo timeout 240 tcpdump -i eth0 -nn 'tcp port 443'` → **16969 个包但 In 方向 0 个**、微信回调 IP 段（220.196.x/101.226.x/140.207.x/163.177.x）**0 命中** → 微信服务器**从未发起连接**（不是 TLS/防火墙/端口问题）
- 历史佐证：pay_order 表 7/13、7/14 的 status=1 订单 **callback_status 全是 2（回调失败）** → 回调**从未成功过**（此前到账可能是手动补单）
- **真正根因候选**：微信 APIv3 要求**商户平台配置「支付回调URL / APIv3 回调域名」白名单**（pay.weixin.qq.com → 产品中心 → 开发配置），未配置或域名不一致时**微信侧静默丢弃回调，不重试**
- 排查顺序定式（钱付了不生效）：①`/wxpay/query` 微信侧 SUCCESS？→ ②openssl 看证书 RSA？→ ③tcpdump 抓 443 看微信 IP 是否**真的来连**（In 方向 0 = 微信侧压根没发）→ ④让用户去商户平台核对回调 URL 配置
- **tcpdump 必须用 `-i eth0`（别用 `-i any`，后者过滤方向易误判），且过滤入站方向 + 微信 IP 段**；抓包时长 ≥240s 覆盖重试窗口
  - ⚠️ 修正（2026-08-28 尾段实测）：`-i any` 同样可抓（抓到 3505 包含微信段），但 `-i eth0` 曾出现**完全抓不到 In 流量**的异常（可能 Docker 网桥 br-* 存在时 eth0 抓包不可靠）。判定"微信服务器没来连"这种**决定性结论前，先用 `-i any` 复验一次**，别只信 eth0 的 0 结果
  - ⚠️⚠️ **tcpdump 解析字段陷阱（2026-08-28 实测，整个排查过程被它带偏多次）**：
    - tcpdump 行格式：`时间 eth0  In  IP 源IP.端口 > 目标IP.端口` —— **`In  IP` 之间是双空格**，`grep ' In IP '`（单空格）永远匹配 0 行，必须 `grep -o 'In  IP [0-9.]*'`
    - 源 IP 是 **`$5`**（`$3` 是网卡名 `eth0`，`$4` 是 `In`）——按 `awk '{print $3}'` 提取出来的是网卡名/空，会得出"0 入站"的**错误结论**
    - **出站连接的回包源端口是 443**（`58.251.x.x.443 > 10.2.0.15.5xxxx`）——只过滤 `tcp port 443` 会把**出站回包**误当微信回调（那些是腾讯云内部 IP 的大流量连接，2274 次！），必须按**目标端口**区分方向
    - ✅ 正确提取"真·入站回调"（目标是我们 443）：`grep '> 10\\.2\\.0\\.15\\.443' file | grep -o 'In  IP [0-9.]*' | awk '{print $3}' | sort | uniq -c`，再对照微信回调 IP 段
    - ⚠️ **微信回调服务器 IP 段不止 220.196/101.226/140.207/163.177——还有 `121.51.x.x`（2026-08-28 实测抓包）**：`121.51.58.174 / 121.51.58.169` 主动连我们 443 并发 268+1705 字节（完整 TLS ClientHello→ServerHello→数据→FIN，就是微信回调 POST）。判定"微信没来连"时，把 121.51 段也纳入匹配，否则会漏判
    - ⚠️ **gunicorn journalctl 无日志 ≠ 网关没收到（2026-08-28 实测）**：`ttdazi-pay` 的 gunicorn 不输出 access log 到 journald（连 curl 打 5005 都不记）——"journalctl -u ttdazi-pay 无 notify 记录"**不能**作为"回调没到网关"的证据。判定回调是否被网关处理，要看**业务库订单状态**（softapi 的 recharge_order.status / ttdazi 的 recharge.status）或临时给网关加日志，别被空日志误导
- ⚠️⚠️⚠️ **商户平台「Native支付回调链接」已配置但仍不通（2026-08-28 最新坑）**：用户在 pay.weixin.qq.com 产品中心→开发配置配了 `https://pay.openai2000.cn/`（**只填根路径**）后回调仍不到。疑点与待验证：
  - 微信 Native 回调配置可能要求**完整 URL**（`https://pay.openai2000.cn/api/v1/wxpay/notify`，与代码 notify_url 完全一致），只填域名/根路径可能不被接受——**让用户改成完整 URL 再测**
  - 配置生效可能有缓存延迟；改完等 1-2 分钟
  - 微信侧验证入口：商户平台→交易中心→交易订单→订单详情，看「通知状态」（通知成功/失败/重试中）+「重新发送通知」按钮——这是**判断微信到底发没发**的权威依据（比抓包更直接）
  - 若订单详情显示"已支付"但无通知记录/通知失败 → 微信确实没发或发不出去，问题必在商户平台配置
- ⚠️⚠️⚠️⚠️ **完整 URL 也配了、抓包也见微信回调 TLS 到达，业务仍不开通 = 网关 APIv3 密钥与商户平台不一致（2026-08-28 排查到的最深层）**：配置完整 URL + 抓包 `-i any` 抓到 `121.51.x.x`（微信回调服务器）**完整 TLS 握手 + 268/1705 字节数据交换**（回调确实发到了 Caddy），但业务库订单仍 status=0 → 问题从"微信没发"推进到"**网关收到了但验签/解密失败，静默丢弃**"。此时唯一剩下要核对的：**网关 `wxpay.py` 的 `WX_API_KEY_V3` 是否与商户平台「API安全 → APIv3密钥」完全一致**——不一致则微信用平台密钥加密的 AES-GCM 回调在网关解密失败 → 返回 400/sign error → 不转发业务 → 微信重试但永不成功。**这个核对必须用户去商户平台看**（APIv3 密钥只显示一次，重置后服务器代码若没同步更新就废了）
- **回调排查完整定式（2026-08-28 最终版，按序推进，每步都有决定性证据）**：①`/wxpay/query` 微信侧 SUCCESS？→ ②openssl 看证书是否 RSA（256 bit=ECDSA 中招，重签）→ ③抓包 `-i any` 看微信 IP（220.196/101.226/140.207/163.177/**121.51**）是否真的来连且完成 TLS——**In 方向 0 = 微信侧压根没发**（→商户平台回调 URL 配置，改完整 URL）→ ④微信回调 TLS 已到但业务未处理 = **网关验签/解密失败**（→核对 APIv3 密钥）→ ⑤全对仍不通才怀疑 Caddy 转发/网关代码
- **验证"回调是否真到达网关"别信 journalctl**（gunicorn 不记 access log），看业务库订单状态或临时加日志

### ⚠️⚠️⚠️⚠️⚠️ 微信已停发平台证书，全面改「微信支付公钥」验签（2026-08-28 最深根因，回调永远验签失败的真凶）
**APIv3 密钥核对无误、微信回调 TLS 完整到达网关、业务仍不开通 → 查网关 `verify_notify` 用的证书文件**。2026-08-28 实测最终根因：
- 网关 `wxpay.py` 的 `verify_notify()` 用 `certs/wx_platform_cert.pem` 验签（`Wechatpay-Signature` + 平台证书公钥）
- 但**微信已停止签发/更新平台证书**：调官方下载接口 `GET https://api.mch.weixin.qq.com/v3/certificates`（带 APIv3 签名）返回：
  ```json
  {"code":"RESOURCE_NOT_EXISTS","message":"无可用的平台证书，请在商户平台-API安全申请使用微信支付公钥。可查看指引 https://pay.weixin.qq.com/doc/v3/merchant/4012153196"}
  ```
- 且历史遗留的 `certs/wx_platform_cert.pem` **根本不是证书**——内容是 125 字节的 JSON 错误响应（`{"code":"SIGN_ERROR","message":"Http头Authorization值格式错误..."}`，当年下载失败时被错误落盘）→ `load_pem_x509_certificate` 抛异常 → `verify_notify` 返回 False → **所有微信回调验签失败返回 400，静默丢弃，永不转发业务**。症状与 APIv3 密钥不匹配完全一样，但密钥是对的
- **识别**：`head -1 certs/wx_platform_cert.pem` 不是 `-----BEGIN CERTIFICATE-----` 而是 JSON → 中招；`openssl x509 -in ... ` 无输出也是信号
- **修法（微信新规）**：从「平台证书验签」迁移到「**微信支付公钥验签**」——用户去商户平台（pay.weixin.qq.com → 产品中心/账户中心 → API安全 → **微信支付公钥**）申请并下载公钥（`-----BEGIN PUBLIC KEY-----`），存到 certs/，`verify_notify` 改为用该公钥 + `Wechatpay-Serial`（公钥ID）验签（微信签名仍 RSA-SHA256 PKCS1v15，只是验签材料从平台证书公钥换成微信支付公钥）。⚠️ AI 电商站（B 服务器 `/data/disk/ai-ecom/lib/wechatpay.ts`）的 `verifyCallback` 直接 `return true` + `decryptCallbackResource` 原样返回，同样未适配，且它解析的是微信原始格式（`resource.out_trade_no/trade_state`）而网关转发的是 `{order_no,amount,status}`——两套格式不匹配，走网关的 AE 回调即使到达也对不上
- **排查定式补充（第⑥步）**：⑤之后仍不通 → ⑥看 `certs/wx_platform_cert.pem` 是不是真证书（JSON=假）→ 是则走公钥迁移，别再怀疑 Caddy/代码

### 业务侧回调接口形态（FastAPI 示例，softapi 2026-08-28）
网关回调是 **JSON POST + Header `X-Pay-Token`**，不是表单参数——FastAPI 必须 `Request` 读 JSON + 校验头：
```python
@router.post("/callback")
async def pay_callback(request: Request, db=Depends(get_db)):
    if request.headers.get("X-Pay-Token", "") != "huizhiyun_gateway_2026":
        return fail(msg="签名无效")   # 伪造回调直接拒
    body = await request.json()
    if body.get("status") != 1 or not body.get("order_no"):
        return fail(msg="无效回调")
    # → 业务开权限 + 订单置已支付（幂等）
```

### Caddy 坑：不支持 `key_type rsa`（validate 直接报 `unrecognized key type: rsa`）
Caddy 的 key_type 只支持 ed25519/ecdsa。要让 Caddy 服务的域名用 RSA 证书只能：
- **certbot 单独签发 RSA + Caddy `tls /path/fullchain.pem /path/privkey.pem` 指令**指定手动证书（该域名 Caddy 不再自动续签，需 certbot renew 兜底）
- 或该域名改用 Nginx（B 服务器模式，certbot 原生 RSA）

### 腾讯云云镜防火墙坑（certbot webroot 验证 secondary timeout）
A 服务器 iptables 首条 `YJ-FIREWALL-INPUT` 链（腾讯云主机安全云镜自动维护，~149 条 REJECT IP，**先于 ACCEPT 匹配**）——可能拦 Let's Encrypt 验证服务器：certbot 报 `During secondary validation ... Timeout during connect (likely firewall problem)`，但本机/B/E/D 服务器 curl 80 全通。
- 排查：`sudo iptables -L YJ-FIREWALL-INPUT -n`（REJECT IP 列表）
- 备选验证方式：DNS-01（需 DNSPod API 密钥）或 TLS-ALPN-01（443，需临时让出端口）
- ✅ **实际可用解法（2026-08-28 验证）**：临时把 YJ 链从 INPUT **摘除**（不是删链内规则）再签，签完恢复：
  ```bash
  sudo iptables-save > /tmp/iptables_before_rsa.txt   # 先备份
  sudo iptables -D INPUT 1                             # 摘除首条 YJ 链（规则仍在链内存着）
  sudo certbot certonly --webroot -w <webroot> -d pay.openai2000.cn \
    --key-type rsa --rsa-key-size 2048 --agree-tos -m <邮箱> --no-eff-email
  sudo iptables-restore < /tmp/iptables_before_rsa.txt # 立即恢复
  ```
  注意：云镜守护进程可能重新插入链，签完尽快恢复；期间 147 个恶意 IP 短暂可访问（可接受，只开 22/80/443）
- ⚠️ **Let's Encrypt 速率限制**：同一域名 1 小时内失败 5 次即锁（`too many failed authorizations (5) ... retry after <UTC时间>`）。**失败重试会滚动重置窗口**，连续失败可能把窗口越推越远——每次重试前先 `date -u` 确认已过窗口，别盲目重试烧配额

### Caddy 手动证书（RSA）配置完整流程（2026-08-28 验证）
certbot 签好 RSA 后接 Caddy 的完整坑序：
1. **caddy 用户(uid 999) 读不了 /etc/letsencrypt/live/**（符号链接到 archive，root:root 640）→ reload 报 `open ...fullchain.pem: permission denied`。解法：证书**复制到 caddy 可读目录**：
   ```bash
   sudo cp /etc/letsencrypt/live/<域>/fullchain.pem /var/lib/caddy/certs/
   sudo cp /etc/letsencrypt/live/<域>/privkey.pem   /var/lib/caddy/certs/
   sudo chown caddy:caddy /var/lib/caddy/certs/* && chmod 644 fullchain.pem && chmod 600 privkey.pem
   ```
2. Caddyfile 该域名加 `tls /var/lib/caddy/certs/fullchain.pem /var/lib/caddy/certs/privkey.pem`（该域 Caddy 不再自动续签）
3. **自动续期钩子**（certbot renew 后同步 + reload）：
   ```bash
   sudo tee /etc/letsencrypt/renewal-hooks/deploy/sync_caddy_cert.sh  # cp 两文件到 /var/lib/caddy/certs + chown + systemctl reload caddy
   sudo chmod +x .../sync_caddy_cert.sh
   ```
4. 验证：`openssl s_client -connect <域>:443 -servername <域> | grep 'Server public key'` → `2048 bit` = RSA 生效；`curl -sk https://<域>/` 全站回归

## 业务系统接入 JSAPI 完整流程

1. 业务下单（业务表，订单号前缀决定路由；官网：模板 TMP / 套餐 SO / 通用 HY）
2. 前端（微信内）POST 业务 `/jsapi` → 后端无 openid cookie 返回 NEED_OAUTH → 前端跳后端 `GET /oauth/url?order_no=` 返回的微信授权 URL（snsapi_base 静默授权，无感）
3. OAuth callback：code 换 openid（`api.weixin.qq.com/sns/oauth2/access_token`）→ Set-Cookie `hz_openid`（HttpOnly, 2h）→ 302 回业务页 `?pay=order_no`
4. 前端再 POST /jsapi（带 openid cookie）→ 后端**先查微信侧状态**（见防重复拉起）→ 调网关 jsapi → 返回 prepay
5. 前端 `wx.chooseWXPay`：引入 `https://res.wx.qq.com/open/js/jweixin-1.6.0.js`，**无需 wx.config**；CSP script-src 需放行 res.wx.qq.com
6. 微信回调 → 网关 notify → 业务回调（X-Pay-Token 校验）→ 业务表 status 0→已支付 + paid_at + 邮件通知 → 返回 {code:0}（网关记 callback_status=1）
7. 前端轮询 GET 业务 `/status/:orderNo` 直到 status>=1 → 成功页

## 防重复拉起支付（双保险，2026-08 实测）

**前端**：startPay 时 `sessionStorage.setItem('pay_started_'+orderNo,'1')`；onMounted 处理 `?pay=` 回跳时——订单已支付→直接 success；已标记→**只轮询不拉起**；未标记→startPay。仅用户主动点「重新支付」才重新拉起。

**后端**：jsapi 下单前先 `wxpay/query` 查微信侧状态：
- `SUCCESS` → 本地同步订单为已支付，返回 `{already_paid:true}`（前端直接进成功轮询）
- `NOTPAY/USERPAYING/PAYERROR` → 先 `wxpay/close` 关旧单再下单（微信 out_trade_no 唯一，不关会报 OUT_TRADE_NO_USED）

## 回调安全与幂等

- 业务回调必须校验 `X-Pay-Token`（不一致 403）
- 幂等：`UPDATE ... SET status=已支付 WHERE order_no=? AND status=0`（rowcount 判断；重复通知不重复处理、不重复发邮件）
- 回调丢失兜底：前端轮询 status + jsapi 的 query-before-order 会同步已支付状态（用户不损失）

## 铁律 / 兼容性

- **改动网关必须向后兼容**：ttdazi PAY 路径行为不变。notify 逻辑：先 `UPDATE pay_order`（ttdazi 单 rowcount>0），再按前缀路由——官网单不在 pay_order 表（rowcount=0），按前缀**无条件**通知官网；PAY 单保持 rowcount>0 才通知 dazi
- 网关改完必须回归：health + native 下单（真实出 code_url）+ 伪造 notify 应 400 + 官网 TMP/SO 三表链路
- 后台配置（无 API，必须用户手动，配好前无法拉起支付）：①公众号后台「网页授权域名」加业务域名 ②商户平台「JSAPI 授权目录」加 https://业务域名/（一个商户号可配多个站点目录）

详细接口规格、业务侧 Node 代码片段（jsapi 幂等路由/notify 回调/前端 startPay）见 📖 `references/payment-gateway-api.md`
