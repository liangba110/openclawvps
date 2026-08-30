# API 字段名不匹配排查

## 收藏页 playmate_id vs companion_id

**症状**：点击收藏跳转「缺少陪玩师ID」，URL 显示 `#/detail/undefined`
**根因**：前端模板用 `item.playmate_id`，API 返回 `item.companion_id`
**修复**：`item.playmate_id` → `item.companion_id`

## 通用排查方法

当页面报告「缺少 XX ID」时：

1. 检查前端模板引用字段名：`grep -n "playmate_id\|companion_id" Favorites.vue`
2. 检查 API 实际返回字段：`curl API_URL | python3 -m json.tool`
3. 对比两字段是否一致
4. 如果后端返回字段名不同，要么改后端加别名，要么改前端匹配

## 常见字段名不匹配模式

| 前端用 | API 返回 | 场景 |
|--------|---------|------|
| `playmate_id` | `companion_id` | 收藏列表/详情跳转 |
| `id_number` | `id_card` | 实名认证详情 |
| `real_name` | `name` | 用户资料 |
| `avatar` | `avatar_url` | 头像展示 |
