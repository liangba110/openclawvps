# 信息撮合下单流程

## 背景

合规要求下，平台不应"售卖陪玩服务时长"，而应定位为"信息中介撮合"。

## CreateOrder.vue 改造

旧版：选择游戏→选择时长(1h/2h/包夜)→选择时间→支付服务费
新版：展示游戏搭档信息→支付信息匹配服务费¥10→获取联系方式

### 模板变更

| 区域 | 旧 | 新 |
|------|----|----|
| 标题 | 确认订单 | 信息匹配 |
| 游戏/时长选择 | 可选，带价格联动 | ❌ 移除 |
| 服务时间选择 | 立即开始/预约时间 | ❌ 移除 |
| 价格 | 服务费（基于时长） | 信息匹配服务费 ¥10 |
| 说明 | 无 | 信息对接说明（3条） |
| 按钮 | 微信支付 ¥xxx | 微信支付 ¥10 |

### 信息对接说明

```html
<div class="info-card">
  <div class="info-title">📋 信息对接说明</div>
  <div class="info-item">✅ 支付信息匹配服务费后，可获取该搭档的联系方式</div>
  <div class="info-item">✅ 匹配成功后，双方自行沟通服务细节</div>
  <div class="info-item">✅ 平台仅提供信息中介服务，不参与双方沟通与服务履行</div>
</div>
```

### 支付流程

前端只跳转，不创建订单（避免双订单）：

```javascript
const token = localStorage.getItem('token')
location.href = 'https://pay.openai2000.cn/pay?token=' + encodeURIComponent(token) + '&amount=10&subject=' + encodeURIComponent('信息匹配服务-' + nickname.value)
```

### 相关变更

- Detail.vue：按钮从「立即预约」改为「立即对接」
- Profile.vue：入口名称从「充值中心」改为「信息服务」
- Recharge.vue：从单金额选择改为套餐卡片（单次/套餐/包月）
- 微信支付备注：`同途搭子-信息匹配服务¥{amount}`
