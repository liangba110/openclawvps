# 需求大厅付费发布（2026-08-03 实现）

## 业务规则（用户确认版 · 2026-08-03 两次迭代定稿）
发布需求必须：**设置服务时长 + 用户自设每小时价格 + 支付对应费用** 才可发布上架。

- **每小时价格由用户自设，范围 ¥30 ~ ¥200**（前后端双重校验：后端 `price<30` 拒绝、`price>200` 拒绝；前端 input min/max + 提交前校验 + 超界红字提示）
- 发布费 = **用户自设每小时价格 × 服务时长**（时长 1-24 小时，前端选项 1,2,3,4,6,8）
- ⚠️ 第一版是固定 ¥10/小时（site_config `demand_publish_price`），用户改为自设价格后该配置已**弃用**——服务端不再读它，改为校验用户传入的 price 参数
- 支付前需求 status=0（待支付，大厅不可见）
- 支付成功回调后 status=1（已发布，大厅可见）
- 需求大厅列表只显示 status=1 的需求

## 状态语义（与预约制订单状态机区分）
```
demand_order.status: 0=待支付 1=待响应(已发布) 2=已响应 3=已完成 4=已取消
```

## 后端改动
### demand.py `/api/demand/create`
- 原 `return fail("发布功能已关闭")` 被重新启用（记忆：发布功能曾因合规/未完成被关闭）
- 参数：title / description / game_id / service_duration（1-24 小时校验）
- 价格**后端计算**（不信任前端传价）：`price = hourly_fee × service_duration`
- 订单号前缀 `DMD`（区别于 orders 表的 HYZ 前缀、recharge 的 CZ/JS 前缀）——支付回调按前缀分流
- INSERT 时 status=0；返回 `{order_no, demand_id, amount}` 供前端跳支付

### pay_api.py `/api/pay/notify/recharge` 加 DMD 分流
支付服务支付成功后回调该接口（POST/GET 都支持，`order_no` + `status=1`），在 recharge 逻辑前插：
```python
if order_no.startswith('DMD'):
    # UPDATE demand_order SET status=1 WHERE order_no=%s AND status=0
    # rowcount>0 → 返回 {'code':0,'msg':'demand_paid'}
```
支付回调里每个业务前缀一个分支（recharge 已存在，DMD 新增），避免相互干扰。

### demand.py `/api/demand/list`
列表过滤从 `d.status=0` 改为 `d.status=1`（只显示已支付需求）。

## 前端改动（MyDemands.vue）
- 顶部「发布需求」→ `openPublish()` 打开弹窗（不再直接跳转）
- 弹窗：标题输入 + 描述 textarea + 服务时长选项（1,2,3,4,6,8 小时 grid，实时显示 `¥单价×时长`）+ 发布费用合计
- `submitPublish()`：`POST /demand/create` 后跳 `pay.openai2000.cn/pay?token=..&amount=..&order_no=DMD单号&subject=需求发布-标题&redirect=/my-demands`
- 列表状态 tab 改 待支付(0)/待响应(1)/已响应(2)/已完成(3)/已取消(4)
- status=0 的需求显示「💚 去支付」按钮（`payDemand()` 重新跳支付，amount=d.price）

## 全链路验证（无 UI 直测）
```bash
# 1. 创建需求（2小时=¥20，服务端算价）
TOKEN=$(cd /opt/ttdazi/backend && sudo -u ubuntu /usr/bin/python3.12 -c 'from app.token_auth import gen_token; print(gen_token(10001,"t"))')
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  http://127.0.0.1:5002/api/demand/create \
  -d '{"title":"测试需求","description":"...","game_id":9,"service_duration":2}'
# → {"code":0,"data":{"amount":20.0,"demand_id":74,"order_no":"DMD2026..."}}
# 2. 模拟支付回调（绕开真实微信支付）
ORDER_NO=$(mysql -N -e 'SELECT order_no FROM demand_order ORDER BY id DESC LIMIT 1')
curl -X POST http://127.0.0.1:5002/api/pay/notify/recharge \
  -H 'Content-Type: application/json' -d "{\"order_no\":\"$ORDER_NO\",\"status\":1,\"amount\":20}"
# → {"code":0,"msg":"demand_paid"}
# 3. 验证：数据库 status 0→1，/api/demand/list 包含该需求
# 4. 清理：DELETE FROM demand_order WHERE id=.. AND title LIKE '测试需求%'
```

## 陷阱
- `site_config` 表 `key` 是 MySQL 保留字，SQL 必须反引号；bash heredoc 里写 `\`key\`` 会被反引号求值——用 `cat > /tmp/x.sql << 'SQLEOF'`（带引号的 heredoc 不展开）+ `mysql < /tmp/x.sql` 执行，避免命令行 -e 转义地狱
- `get_site_config('demand_publish_price', '10')` 的 default 参数是 **str**（Pyright 会报 int 不匹配），传 `'10'` 再 float()——但自设价格后此配置已弃用
- 需求发布实名认证校验仍保留（verify_status=1 才能发布）

## 信息匹配服务费已取消（2026-08-03）
用户决定**取消「信息匹配服务费」（¥10 那种）**，平台收费只剩两笔：达人置顶展示费（包月¥79/包季¥199/包年¥599）+ 预约服务费（¥30-200/小时）。同步清理三处：
- **DemandHall.vue**：需求卡片的「🔓 付费解锁 ¥10」按钮 → 改为「💬 私聊沟通」；删除 `payForDemand()` 函数；注意原按钮下方 foot 区已有 goChat 按钮，改完会重复，删掉一处
- **Profile.vue**：删除「信息服务（购买信息匹配套餐）」菜单项（跳 /recharge 那个）
- **Agreement.vue**：用户协议「三、信息匹配服务费」条款 → 「三、服务费用规则」（展示费+预约费+结算说明）；平台规则「六、服务费规则」→ 新费用规则（¥79/199/599 + ¥30-200/小时 + 退款规则）
