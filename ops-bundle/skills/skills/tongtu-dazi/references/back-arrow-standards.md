# 全站返回箭头统一标准

## 样式规范

所有页面的返回箭头使用统一样式：

| 属性 | 值 |
|------|-----|
| 字号 | **28px** |
| 颜色 | **#fff**（白色），非渐变/深色背景用 `#667eea` |
| 符号 | **‹**（左单箭头，不是 ←） |
| 交互 | `@click="smartBack(route.path)"` |
| 字体 | `line-height: 1` |
| 光标 | `cursor: pointer` |

## 三种布局模式

### 模式A：标准 header-bar（推荐，80% 页面适用）

```vue
<div class="header-bar">
  <span class="back" @click="smartBack(route.path)">‹</span>
  <span class="title">页面标题</span>
  <span class="right"></span>
</div>
```

```css
/* 全局 CSS（global.css 已预置） */
.header-bar {
  display: flex; align-items: center;
  background: linear-gradient(135deg, #667eea, #764ba2);
  padding: 44px 16px 14px; color: #fff;
}
.header-bar .back {
  font-size: 28px; cursor: pointer; line-height: 1; color: #fff;
}
```

适用页面：Orders, Settings, Messages, MessageDetail, Reviews, Favorites, Coupons, About, Agreement, Security, VerifyIdentity, CreateOrder, MyFeedback, CustomerService

### 模式B：自定义 header + absolute .back（Profile 等特殊页）

Profile 页使用自定义 `profile-header`（非 header-bar），返回箭头用 absolute 定位：

```vue
<div class="profile-header">
  <div class="back" @click="smartBack(route.path)">‹</div>
  ...avatar, 用户名, 统计...
</div>
```

```css
.profile-header .back {
  position: absolute; top: 8px; left: 14px;
  font-size: 28px; cursor: pointer; color: #fff; z-index: 10;
  line-height: 1;
}
```

### 模式C：浮动圆标（Detail 等需要覆盖在图片/视频上的页）

```vue
<div class="back detail-back" @click="smartBack(route.path)">‹</div>
```

```css
.detail-back {
  position: absolute; top: 12px; left: 12px; z-index: 10;
  font-size: 28px; color: #fff; cursor: pointer;
  line-height: 1;
}
```

可选：加半透明背景方便阅读：
```css
.detail-back {
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.15);
  border-radius: 50%; backdrop-filter: blur(4px);
}
```

## 所有页面清单

| 页面 | 模式 | 状态 |
|------|------|------|
| Orders.vue | A header-bar | ✅ |
| Settings.vue | A header-bar | ✅ |
| Messages.vue | A header-bar | ✅ |
| MessageDetail.vue | A header-bar | ✅ |
| Reviews.vue | A header-bar | ✅ |
| Favorites.vue | A header-bar | ✅ |
| Coupons.vue | A header-bar | ✅ |
| Coupon.vue | A header-bar | ✅ |
| About.vue | A header-bar | ✅ |
| Agreement.vue | A header-bar | ✅ |
| Security.vue | A header-bar | ✅ |
| VerifyIdentity.vue | A header-bar | ✅ |
| CreateOrder.vue | A header-bar | ✅ |
| MyFeedback.vue | A header-bar | ✅ |
| CustomerService.vue | A header-bar | ✅ |
| Profile.vue | B profile-header absolute | ✅ |
| Detail.vue | C detail-back absolute | ✅ |
| List.vue | A（gradient-header 变体） | ✅ |
| Download.vue | A（半透黑底 header-bar） | ✅ |
| Verification.vue | A（login-card 内左对齐） | ✅ |
| TeamBoard.vue | C fixed 定位 | ✅ |

不需要返回箭头的页面：Login, Register, EmailRegister, FollowRegister, Home, CompanionRegister

## 实现检查清单

1. **`smartBack` 导入** — 在 `<script setup>` 中添加 `import { smartBack } from '@/utils/nav'`
2. **回到页** — `nav.js` 中配置 `'/page-path': '/parent-path'` fallback
3. **隔离 `.back` CSS** — scoped style 中 `.back` 不会污染全局，但需注意全局 `.header-bar .back` 在 scoped 中可能被覆盖
4. **颜色适配** — 深色/图片背景上用白色，浅色背景上用 `#667eea`
