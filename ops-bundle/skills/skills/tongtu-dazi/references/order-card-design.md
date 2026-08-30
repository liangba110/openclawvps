# 订单卡片设计规范

## 卡片布局

```
┌──────────────────────────────────────┐
│ 🆔 HYZ20260706142356xxxx    待支付   │  ← order-top: 订单号+状态
├──────────────────────────────────────┤
│ [头像] 小甜心              ¥25.00    │  ← order-mid: 左信息+右金额
│        王者荣耀                      │
│        📅 2026-07-06 🕐 14:23        │
│        ⏱ 1小时                      │
│        📝 求带飞🥇                    │
├──────────────────────────────────────┤
│              💚 去支付  取消          │  ← order-actions
└──────────────────────────────────────┘
```

## 关键样式参数

| 元素 | 属性 | 值 |
|------|------|----|
| 卡片 | padding | `10px 14px` |
| 订单号区 | padding-bottom | `8px` |
| 订单号区 | margin-bottom | `8px` |
| 分隔线 | border-bottom | `1px dashed #f0f0f0` |
| 数据标签 | margin-top | `4px` |
| 数据标签 | 内边距 | `1px 6px` |
| 数据标签 | gap | `4px` |
| 备注行 | margin-top | `4px` |
| 备注行 | padding | `2px 8px` |
| 操作按钮区 | margin/padding-top | 各 `8px` |
| 卡片间距 | gap | `10px` |
| 列表外间距 | padding | `10px 14px` |

## 头像显示

```vue
<div class="c-avatar-wrap">
  <img v-if="order.avatar && (order.avatar.startsWith('http') || order.avatar.startsWith('/'))"
       :src="order.avatar" class="c-avatar-img" @error="handleAvatarError(order)" />
  <div v-else class="c-avatar">{{ (order.nickname || '?')[0] }}</div>
</div>
```

优先显示真实头像 URL，加载失败降级为渐变紫底昵称首字。
