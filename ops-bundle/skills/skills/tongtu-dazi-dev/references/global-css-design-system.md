# Global CSS Design System — 页面统一规范

When user asks "调成统一样式" (style unify), apply this shared design system. Defined in `frontend/src/assets/global.css`.

## 核心类库

| Class | 用途 | 说明 |
|-------|------|------|
| `.page` | 页面容器 | `min-height:100vh`, `background:#f5f6fa`, `padding-bottom:80px` |
| `.header-bar` | 渐变顶栏 | flex 14px padding, 渐变紫 #667eea → #764ba2, 白色文字 |
| `.card` | 白色卡片 | 12px radius, 16px padding, 12px margin, shadow |
| `.menu-item` | 菜单项 | 白卡+阴影, 内含 .mi-icon/.mi-info/.mi-title/.mi-desc/.mi-arrow |
| `.btn-primary` | 渐变按钮 | 10px radius, 渐变紫背景, 白色文字, disabled 半透明 |
| `.input-field` | 统一输入框 | 1px #eee 边框, 10px radius, focus 紫色 |
| `.badge` | 标签 | 5 色: blue/green/red/orange/purple |
| `.empty-state` | 空状态 | icon + text |
| `.form-group` | 表单组 | label + input wrapper |
| `.section-label` | 分段标题 | 13px, 灰色, bold |

## ⚠️ 老类名 vs 新类名 — 静默不一致陷阱

Profile.vue 历史上用的老类名: `micon/minfo/mt/ms/arrow`
新设计系统用: `mi-icon/mi-info/mi-title/mi-desc/mi-arrow`

混合使用 IDE 看着对，但渲染样式不同：

```html
<!-- ❌ OLD — 依赖 scoped CSS .micon/.minfo/.mt
<div class="micon" style="background:rgba(102,126,234,0.1)">📄</div>
<div class="minfo"><div class="mt">用户协议</div></div>
<span class="arrow">›</span>

<!-- ✅ NEW — 全局类
<div class="mi-icon" style="background:rgba(102,126,234,0.1)">📄</div>
<div class="mi-info"><div class="mi-title">用户协议</div></div>
<span class="mi-arrow">›</span>
```

**为什么看不出来:** 因为 scoped style 里还留着 `.micon/.minfo/.mt` 的样式。Profile 整体看起来一致，但菜单项**实际**走的是不同代码路径。

**迁移检查清单:**
- [ ] `class="micon"` → `class="mi-icon"`
- [ ] `class="minfo"` → `class="mi-info"`
- [ ] `class="mt"` → `class="mi-title"`
- [ ] `class="ms"` → `class="mi-desc"`
- [ ] `class="arrow"` → `class="mi-arrow"` (在 menu-item 上下文)
- [ ] `class="marrow"` → `class="mi-arrow"`

**验证命令:** `grep -E 'class="(micon|minfo|\bmt\b|\bms\b|arrow|marrow)"' /opt/ttdazi/frontend/src/views/*.vue`

## 已迁移到全局类的页面

- Agreement.vue — `ag-header/ag-card` → `header-bar/card`
- About.vue — `page-header/section` → `header-bar/card`
- Download.vue — 保留暗黑 hero, `.card` 用于密码表单
- Orders/Settings/Security — 主容器 + 按钮标准化
- Favorites/Reviews/Coupons/Messages/MessageDetail — `header-bar` + `card`
- Profile.vue — 全部 9 个菜单项统一使用 `.menu-item` + `.mi-*` 全局类

## smartBack Fallback Map — 匹配入口而非路径

`frontend/src/utils/nav.js` 有 FALLBACK_MAP dict，映射页面路径到返回位置。

**Bug 案例:** Agreement 页面 (`/agreement/user` 等) 最初映射到 `/settings`，但用户实际是从 Profile 菜单点进来的，映射到 `/settings` 是错的。

**修复:**
```js
const FALLBACK_MAP = {
  // ❌ WRONG — '/agreement/user': '/settings',
  // ✅ CORRECT
  '/agreement/user': '/profile',
  '/agreement/privacy': '/profile',
  '/agreement/rules': '/profile',
  '/agreement/disclaimer': '/profile',
}
```

**调试模式:** 当用户反馈"返回按钮去错地方"时:
1. 找到源页面 (链接在哪点击的) — 检查那个页面的 `goTo()` 或 `@click="$router.push"`
2. 更新 FALLBACK_MAP 匹配源