# 全站 3D 立体设计系统

## 全局 CSS 类（定义于 `global.css`）

| 类名 | 用途 | 关键属性 |
|------|------|---------|
| `.card-3d` | 白色立体卡片 | 16px 圆角, 4层紫阴影, perspective rotateX(2deg), 顶部白色高光border+渐变, 紫色微背景, active时变平+上浮 |
| `.menu-item-3d` | 菜单项 | 14px 圆角, 3层紫阴影, perspective rotateX(1deg), 顶部高光border, active时变平+上浮 |
| `.mi-icon` | 38px 方形图标容器 | 10px 圆角, 居中 |
| `.mi-info` | 文字区 | flex:1, overflow:hidden, text-overflow:ellipsis |
| `.mi-title` | 菜单标题 | 14px, #333, bold, 溢出省略 |
| `.mi-desc` | 菜单副标题 | 12px, #999, 溢出省略 |
| `.mi-arrow` | 右箭头 | 20px, #ddd, margin-left:auto 推到最右 |
| `.mi-locked` | 锁定图标 | 12px, right-aligned, padding-left:8px |
| `.header-bar` | 渐变顶栏 | flex, 14px padding, 渐变紫背景, 白色文字 |
| `.btn-primary` | 渐变按钮 | 10px 圆角, 渐变紫 |
| `.input-field` | 输入框 | 1px #eee边框, 10px 圆角 |

## 关键陷阱

### 1. `.menu-item-3d` 不要加 `::before` 伪元素

```css
/* ❌ 错误 — 伪元素会遮挡文字 */
.menu-item-3d::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 45%;
  background: linear-gradient(...);
  border-radius: 14px 14px 0 0;
  pointer-events: none;
}

/* ✅ 正确 — 只在 .card-3d 上保留 ::before */
.card-3d::before { ... }
```

原因：菜单项内部有文字和图标，`::before` 绝对定位会盖在这些内容的上面，即使 `pointer-events: none` 不影响交互，但半透明渐变会遮盖文字的可读性。

### 2. `.menu-item-3d` 内部不要嵌套 `.mi-arrow-group` 包裹 `mi-desc + mi-arrow`

```vue
<!-- ❌ 嵌套导致 margin-left:auto 失效 -->
<div class="menu-item-3d">
  <div class="mi-icon">📋</div>
  <div class="mi-info"><div class="mi-title">标题</div></div>
  <div class="mi-arrow-group">            <!-- ← 冗余包装！ -->
    <span class="mi-desc">描述</span>
    <span class="mi-arrow">›</span>
  </div>
</div>

<!-- ✅ 直接放 flex 子元素，mi-arrow 用 margin-left:auto 对齐 -->
<div class="menu-item-3d">
  <div class="mi-icon">📋</div>
  <div class="mi-info"><div class="mi-title">标题</div></div>
  <span class="mi-desc">描述</span>
  <span class="mi-arrow">›</span>
</div>
```
