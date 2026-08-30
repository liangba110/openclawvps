# 同途搭子 2026-08 关键改造记录（预约制闭环 / Token / 支付反代 / 品牌资源）

本文记录 2026-08 上线的可复用技术细节。改造均已实测通过并部署到
主站 dazi.openai2000.cn + 国际站 www.ttdazi.xyz。

## 1. 预约制服务闭环（订单状态机改造）

用户确认的业务模式：**用户预约→支付全款→达人接受→约定信息→开始服务⏱倒计时→
倒计时自然结束→用户确认/3天自动确认→结算（佣金15%可配）→三档评价（好评/一般/差评，无需审核自动展示，仅成交用户可评，达人可回复）**。

### 订单状态机（新）
```
0=待支付  1=待接单(已支付)  2=已接受(达人接受)  3=服务中(倒计时中)
4=待确认(倒计时结束)  5=已完成(已结算)  6=已取消/已退款
```
旧状态机（0待支付/1待接单/2服务中/3完成/4取消）已废弃。**不允许提前结束**
（达人不可、用户不可，倒计时自然走完；特殊纠纷走管理端手动结束）。

### 数据库
- `orders` 新增字段：`service_date`(预约时间)、`service_duration`(预约时长小时)、
  `service_started_at`、`service_ended_at`(倒计时终点=started+duration)、
  `confirm_deadline`(确认截止)、`auto_confirmed`(是否自动确认)
- `site_config`：`commission_rate`(平台抽成%，默认15，后台可改)、
  `auto_confirm_days`(默认3)、`service_durations`(1,2,3,4,6,8)

### 后端
- 现有 `playmate/accept-order`(1→2) 语义正好匹配"接受预约"，直接复用
- `playmate/complete-order` 改造为"开始服务"(2→3，写 started_at + 倒计时终点)
- `playmate/reject-order` 改造为"拒绝预约"(→6 退款)
- 新增：`/api/order/confirm-service`(用户确认4→5+结算)、`/api/order/detail`、
  `/api/order/refund`(待接单自动退/已接受进管理端)
- 佣金结算在确认时：达人收入=金额×(1-佣金%)，平台佣金=金额×佣金%，写 money_log
- 注意：确认/结算逻辑要写到**用户确认**(confirm-service)和**定时任务自动确认**两个入口

### 定时任务 `app/order_cron.py`（cron_bp，每分钟）
- ① status=3 且 service_ended_at<=NOW → 转4待确认 + 通知用户
- ② status=4 且 confirm_deadline<=NOW → 自动确认5 + 结算
- main.py 注册蓝图 + `crontab` 加：`* * * * * curl -s http://127.0.0.1:5002/api/cron/order-tasks`
- 测试：手改 DB 时间字段模拟倒计时结束/超期 → 跑 curl cron → 查状态流转

### 前端
- 用户端：Detail.vue 预约入口、CreateOrder.vue 预约模式(选时长/日期)、
  新增 OrderDetail.vue(⏱倒计时/确认/三档评价)、Orders.vue 新状态tab
- 达人端：PlaymateOrders.vue 接受/开始服务/等待确认
- 管理端：admin.py 状态映射更新 `{0:pending,1:paid,2:accepted,3:active,4:confirming,5:completed,6:cancelled}`

## 2. 登录过期修复（Token 有效期 + 滚动续期 + 并发去重）

症状：网站过段时间自动退出提示登录过期。

### 根因与修复（三管齐下）
1. **token 有效期太短**：`token_auth.py` `ACCESS_TOKEN_TTL = 7200`(2小时) → `604800`(7天)
2. **refresh 不滚动续期**：`user.py /refresh` 原来只发新 access。改为：验证通过后
   **删除旧 refresh_token、插入新 refresh_token**(48位随机)，返回
   `{'token': 新access, 'refresh_token': 新refresh}`，形成永不中断的续期链
3. **前端并发去重**：`src/api/index.js` 拦截器原来每个 401 都各自发 refresh（并发
   时互相覆盖、旧 token 删除后另一请求又用）。重构为模块级 `refreshing` promise 单例：
   - `doRefresh()` 复用进行中的刷新 promise（`if (refreshing) return refreshing`）
   - 成功：更新 token + refresh_token，重试原始请求（改 Authorization 头）
   - 失败/无 refresh：统一 `clearAuth()` 清 localStorage + 跳登录
   - 同时处理 `res.data.code===401`(HTTP200业务码) 和 `err.response.status===401` 两个分支

### 验证
- `gen_token(uid, dev)` 后 `parse_token` 的 `expires_in` ≈ 604799 秒 = 7天
- 完整链路：登录→拿refresh→token过期→verify_refresh_token→新token

## 3. 支付页域名隐藏（pay.openai2000.cn 反代到自有域名）

需求：点击支付时地址栏不显示 `pay.openai2000.cn`。

### 三层改动（实测）
1. **支付页模板 `payment_service/templates/pay.html`**：把所有硬编码
   `'https://dazi.openai2000.cn'` 替换为 `API_BASE`(=`location.origin`)，开头加
   `var API_BASE = location.origin;`
2. **Nginx 反代**（Server B 主站 + 服务器D 国际站都加）：
   ```nginx
   location ~ ^/pay(/.*)?$ {
       proxy_pass http://42.193.113.230:5005/pay$1;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
   }
   ```
   - ⚠️ 必须直连 **http://42.193.113.230:5005**（Server A 的支付服务端口），
     不能反代 `https://pay.openai2000.cn`（443 无服务会 SSL 握手失败 502）
   - ⚠️ **不要**加 `location = /pay { return 302 /pay/; }` —— 会跟正则块冲突造成
     /pay 302 → /pay/ → 404 循环。正则 `^/pay(/.*)?$` 已覆盖 /pay 和 /pay/ 两种
   - 5005 的 /pay 路由无斜杠才返回 200，/pay/ 404 —— 正则写法正是为兼容这点
3. **前端跳转**：所有 `window.location.href = 'https://pay.openai2000.cn/pay?...'`
   改为 `location.origin + '/pay?...'`（CreateOrder/MyDemands/Recharge 共5处）

### SPA hash 路由跳转规范化（取消支付报错的根因）
- pay.html 的 `myRedirect` 参数是 `/orders`、`/companion/register?activated=1`
  （无 `#/` 前缀），直接 `API_BASE + myRedirect` 会跳成无 hash 的路径 → SPA 白屏/报错
- 修复：`normalizeRedirect(r)`：无#且非http → 补 `/#` 前缀；取消按钮和支付成功
  跳转都用它。后端 `wxpay_confirm` 同样规范化 redirect（`/#` + 当前域名）
- 改完 pay.html 必须重启支付服务：`sudo kill -HUP $(pgrep -f 'gunicorn -b 0.0.0.0:5005')`

## 4. 需求大厅付费发布（用户自设价格 30-200/小时）

- 后端 `demand.py /create`：重新启用（曾关闭）。发布费 = 用户自设每小时价格 ×
  服务时长(1-24h)。价格校验 `<30` 拒绝"每小时价格不得低于¥30"，`>200` 拒绝"不得高于¥200"
- 订单号 `DMD+时间戳+4位随机`，初始 `status=0`(待支付)；支付回调
  `pay_api.py notify/recharge` 增加 DMD 前缀分支：status 0→1(上架可见)
- 需求大厅列表只显示 `status=1`(已支付)；`/my` 返回全部状态
- 前端 MyDemands.vue：发布弹窗(标题/描述/每小时价格¥30-200/时长1-8h)+「去支付」按钮+
  状态适配(0待支付/1待响应/2已响应/3已完成/4已取消)

## 5. 官方品牌 Logo 资源与永久存档

- **官方全套资源目录**：Server B `/home/ubuntu/ttdazi-frontend/brand/`（45个文件：
  logo-horizontal.png 880×340、logo-master.svg/png(蓝紫渐变圆角方块+白色「搭」字+白圆环)、
  icon_512/192/96/72/48/40/32、favicon_16/32/48/64/128/256、favicon.ico、
  wx_avatar_*/wx_square_*/mp_icon_*、同途搭子-全套Logo.zip）
- 展示页：`https://dazi.openai2000.cn/brand/logo-showcase.html`
- **永久存档**：服务器A `/opt/ttdazi/logo-official/`（随每日备份，README 标注"终生使用禁止删除"）
- 替换到网站：public/brand/ 同步三端；Home 导航栏/Login 用 `/brand/logo-horizontal.png`；
  favicon 用 `/brand/favicon_16.png`；PWA manifest icons 用 icon_192/512；
  支付页 logo base64 内联官方 icon_512
- 用户发图核对：md5 比对判断是否同图，尺寸+主色分析识别版本

## 6. 中文字体渲染陷阱（PIL/cairosvg）

- **cairosvg 渲染中文 SVG 会乱码**（找不到中文字体，输出豆腐块/乱码，行分布呈均匀横条）
- 正确：用 PIL + 中文字体直接绘制：`ImageFont.truetype('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', size)`
- 检测乱码：ASCII 字符画分析内容结构（行密度均匀=乱码方块；笔画分段=真字）
- 安装 cairosvg：`pip3 install cairosvg --break-system-packages`（PEP668 环境）

## 7. 部署流程提醒
- 构建在服务器A：`cd /opt/ttdazi/frontend && npm run build`
- 同步：tar dist → Server B `/home/ubuntu/ttdazi-frontend/`（保留 landing.html）→
  服务器D `/var/www/ttdazi/`；chmod 755 dirs / 644 files / chown www-data
- 前端新页面（如 OrderDetail.vue）要确认 chunk 已生成、路由已注册
- 用户浏览器缓存旧版：hash 文件名变了客户端自动拉新；还不行就让用户清缓存
