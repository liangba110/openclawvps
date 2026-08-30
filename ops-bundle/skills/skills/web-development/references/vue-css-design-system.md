# Vue CSS Design System Unification

## Goal

Eliminate duplicated/redundant `scoped` styles across pages. Define shared CSS classes in `global.css` so every page can use `class="page header-bar card-3d btn-primary input-field"` instead of redefining the same 30 lines per component.

## The Pattern

### 1. Define design tokens in `global.css`

```css
/* ==================== 统一页面设计系统 ==================== */

/* 页面容器（带底部安全区） */
.page { min-height: 100vh; background: #f5f6fa; padding-bottom: 80px; }

/* 渐变顶栏 */
.header-bar {
  display: flex; align-items: center; padding: 14px 16px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff; gap: 12px;
}
.header-bar .back { font-size: 22px; cursor: pointer; }
.header-bar .title { font-size: 17px; font-weight: 700; flex: 1; text-align: center; }
.header-bar .right { width: 28px; }

/* 渐变按钮 */
.btn-primary {
  border: none; border-radius: 10px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff; font-size: 15px; font-weight: 600; padding: 12px 0;
  cursor: pointer; text-align: center;
}

/* 输入框统一样式 */
.input-field {
  width: 100%; padding: 11px 14px;
  border: 1px solid #eee; border-radius: 10px;
  font-size: 14px; outline: none; box-sizing: border-box;
}
.input-field:focus { border-color: #667eea; }

/* 标签/徽章 */
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-blue { background: #e3f2fd; color: #1565c0; }
.badge-green { background: #e8f5e9; color: #2e7d32; }
.badge-red { background: #ffebee; color: #c62828; }
.badge-orange { background: #fff3e0; color: #e65100; }
.badge-purple { background: #f3e5f5; color: #7b1fa2; }

/* 空状态 */
.empty-state { text-align: center; padding: 60px 20px; }
.empty-state .empty-icon { font-size: 56px; opacity: 0.4; }
.empty-state .empty-text { font-size: 14px; color: #888; }

/* 表单组 */
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; font-weight: 600; color: #555; }

/* 分段标题 */
.section-label { padding: 4px 16px 8px; font-size: 13px; color: #999; font-weight: 600; }
```

### 2. 3D 立体卡片（`card-3d`）

用在所有白底卡片上，带来统一的立体悬浮效果：

```css
.card-3d {
  position: relative;
  background: #fff;
  border-radius: 16px;
  padding: 14px 16px;
  box-shadow:
    0 1px 0 rgba(255,255,255,0.6) inset,
    0 1px 2px rgba(102,126,234,0.08),
    0 4px 12px rgba(102,126,234,0.12),
    0 8px 24px rgba(118,75,162,0.10);
  transform: perspective(1200px) rotateX(2deg) rotateY(-1deg);
  transform-origin: center center;
  transition: transform 0.35s cubic-bezier(.4,0,.2,1), box-shadow 0.35s ease;
  border-top: 2px solid rgba(255,255,255,0.8);
  background-image: linear-gradient(180deg, rgba(102,126,234,0.04) 0%, rgba(255,255,255,0) 60%);
}
.card-3d:active {
  transform: perspective(1200px) rotateX(0deg) rotateY(0deg) translateZ(8px);
  box-shadow:
    0 2px 4px rgba(102,126,234,0.12),
    0 6px 16px rgba(118,75,162,0.18);
}
.card-3d::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 50%;
  background: linear-gradient(180deg, rgba(255,255,255,0.5) 0%, rgba(255,255,255,0) 100%);
  border-radius: 16px 16px 0 0;
  pointer-events: none;
}
```

### 3. 3D 立体菜单项（`menu-item-3d` + `.mi-*` 命名空间）

用在列表式菜单项上，统一图标+文字+箭头的布局：

```css
.menu-item-3d {
  display: flex; align-items: center; padding: 15px 16px;
  background: #fff; border-radius: 14px; margin-bottom: 10px;
  border-top: 2px solid rgba(255,255,255,0.8);
  background-image: linear-gradient(180deg, rgba(102,126,234,0.03) 0%, rgba(255,255,255,0) 60%);
  box-shadow:
    0 1px 0 rgba(255,255,255,0.6) inset,
    0 1px 2px rgba(102,126,234,0.08),
    0 4px 10px rgba(102,126,234,0.10),
    0 6px 18px rgba(118,75,162,0.08);
  transform: perspective(1200px) rotateX(1deg);
  transform-origin: center center;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  cursor: pointer;
}
.menu-item-3d:active {
  transform: perspective(1200px) rotateX(0) translateZ(6px);
  box-shadow:
    0 2px 4px rgba(102,126,234,0.12),
    0 4px 12px rgba(118,75,162,0.15);
}

/* 全局 .mi-* 命名空间 */
.mi-icon {
  width: 38px; height: 38px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; margin-right: 12px; flex-shrink: 0;
}
.mi-info { flex: 1; min-width: 0; overflow: hidden; }
.mi-title { font-size: 14px; color: #333; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mi-desc { font-size: 12px; color: #999; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mi-arrow { font-size: 20px; color: #ddd; margin-left: auto; flex-shrink: 0; padding-left: 8px; }
.mi-locked { font-size: 12px; color: #999; flex-shrink: 0; margin-left: auto; padding-left: 8px; }
```

**注意**：`.mi-arrow` 必须通过 `margin-left: auto` 推到右侧，不能嵌套在另一个 div 里（如 `.mi-arrow-group`），否则 auto 无效。

### 4. 登录/注册页面（`.login-page` 系列）

4 个登录注册页（Login/Register/EmailRegister/FollowRegister）共用一套全局样式：

```css
.login-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}
.login-bg { position: absolute; inset: 0; pointer-events: none; }
.login-bg .bg-circle { position: absolute; border-radius: 50%; opacity: 0.1; background: #fff; }
.login-bg .c1 { width: 300px; height: 300px; top: -80px; right: -60px; }
.login-bg .c2 { width: 200px; height: 200px; bottom: -40px; left: -40px; }
.login-bg .c3 { width: 150px; height: 150px; top: 50%; left: 50%; transform: translate(-50%, -50%); }

.login-card {
  position: relative; z-index: 1;
  background: #fff; border-radius: 18px;
  padding: 26px 22px; width: 100%; max-width: 380px;
  box-shadow:
    0 1px 0 rgba(255,255,255,0.6) inset,
    0 8px 24px rgba(102,126,234,0.25),
    0 16px 48px rgba(118,75,162,0.25);
}
.login-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 50%;
  background: linear-gradient(180deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0) 100%);
  border-radius: 18px 18px 0 0;
  pointer-events: none;
}
/* 还有 login-logo, login-tabs, login-footer, login-agreement 等 */
```

## Use in templates

```vue
<!-- 普通页面 -->
<template>
  <div class="page">
    <div class="header-bar">
      <span class="back" @click="goBack">‹</span>
      <span class="title">页面标题</span>
      <span class="right"></span>
    </div>
    <div class="card-3d">
      <div>卡片内容</div>
    </div>
    <!-- 菜单项 -->
    <div class="menu-item-3d" @click="doAction">
      <div class="mi-icon">📋</div>
      <div class="mi-info"><div class="mi-title">标题</div><div class="mi-desc">描述</div></div>
      <span class="mi-arrow">›</span>
    </div>
    <div class="form-group">
      <label>输入框</label>
      <input class="input-field" v-model="value" />
    </div>
    <button class="btn-primary" @click="submit">提交</button>
  </div>
</template>
<style scoped>
/* Only keep page-specific styles here */
</style>

<!-- 登录/注册页面 -->
<template>
  <div class="login-page">
    <div class="login-bg"><div class="bg-circle c1"></div><div class="bg-circle c2"></div><div class="bg-circle c3"></div></div>
    <div class="login-card">
      <div class="login-logo"><span class="logo-icon">🎮</span><span class="logo-text">同途搭子</span></div>
      <!-- 表单 -->
    </div>
  </div>
</template>
```

## Migration checklist (single page)

1. ✅ Replace `<div class="page-container">` → `<div class="page">`
2. ✅ Replace custom header → `<div class="header-bar">` with `back`/`title`/`right`
3. ✅ Replace old `.card` → `.card-3d` (3D立体版)
4. ✅ Replace menu items → `.menu-item-3d` + `.mi-icon` / `.mi-info` / `.mi-title` / `.mi-desc` / `.mi-arrow`
5. ✅ Replace buttons → `<button class="btn-primary">`
6. ✅ Replace inputs → `<input class="input-field">`
7. ✅ Remove empty/duplicated `scoped` style blocks entirely when all styles are covered by global classes
8. ✅ Build (`npm run build`) and verify

## Common Pitfalls

### Pitfall 1: `.mi-arrow` inside a wrapper div

The `.mi-arrow` uses `margin-left: auto` to push to the right edge. If you wrap it in another `<div>` (like `<div class="mi-arrow-group">`), `auto` computes from the wrapper, not the `.menu-item-3d`. Always put `.mi-arrow` directly as a child of `.menu-item-3d`:

```vue
<!-- WRONG — margin-left: auto doesn't work on nested div -->
<div class="menu-item-3d">
  <div class="mi-icon">📋</div>
  <div class="mi-info">...</div>
  <div class="mi-arrow-group">   <!-- THIS DIV BLOCKS AUTO -->
    <span class="mi-arrow">›</span>
  </div>
</div>

<!-- RIGHT — arrow is direct child -->
<div class="menu-item-3d">
  <div class="mi-icon">📋</div>
  <div class="mi-info">...</div>
  <span class="mi-arrow">›</span>
</div>
```

### Pitfall 2: `.card-3d ::before` and `::after` on elements with `.menu-item-3d`

`.menu-item-3d` does NOT have a `::before` pseudo-element (unlike `.card-3d`). The pseudo-element was removed from `.menu-item-3d` because it overlapped with text content. If a component needs both card and menu styles, apply only one:

```vue
<div class="card-3d">         <!-- has ::before high light -->
  <div class="menu-item-3d">  <!-- no ::before, safe for text -->
    ...
  </div>
</div>
```

### Pitfall 3: Modal buttons and inputs

Modal buttons need different sizing from global `.btn-primary`. Use combined classes:

```vue
<button class="btn-primary modal-primary-btn">确认</button>
<input class="input-field modal-field" v-model="val" />
<style scoped>
.modal-primary-btn { height: 42px; font-size: 14px; flex: 1; }
.modal-field { margin-bottom: 10px; }
</style>
```

### Pitfall 4: Dark-themed pages

Pages like `Download.vue` (dark gradient background) should NOT adopt `.page` or `.header-bar`. Keep their own layout, only standardize form controls:

```vue
<style scoped>
.dl-page {
  min-height: 100vh;
  background: linear-gradient(135deg,#1a1a2e,#16213e);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.dl-card {
  background: #fff; border-radius: 20px;
  /* 3D shadow but custom to dark background */
  box-shadow: 0 8px 24px rgba(102,126,234,0.3), 0 20px 60px rgba(0,0,0,0.4);
}
</style>
<!-- Use global .input-field and .btn-primary for form controls -->
```

### Pitfall 5: Tabs below header-bar

Tabs go BELOW `.header-bar`, not inside it:

```vue
<div class="header-bar">
  <span class="back">←</span>
  <span class="title">页面标题</span>
</div>
<div class="tab-bar">   <!-- custom, outside header-bar -->
  <span v-for="t in tabs" :key="t" class="tab">...</span>
</div>
```

### Pitfall 6: Badge colors vs custom status classes

Replace custom status badges with global `.badge` variants:

```vue
<!-- WRONG — custom class -->
<div class="coupon-badge">已使用</div>
<!-- RIGHT — global badge -->
<div class="badge badge-orange">已使用</div>
```

But KEEP custom status classes used as background colors on full containers (e.g., `.s0` on order status spans).

### Pitfall 7: Login page scoped styles

Login/Register/EmailRegister/FollowRegister 四个页面共用 `global.css` 中 `.login-*` 类。每个页面的 `scoped style` 只需保留验证码行等独有样式。不重复定义 `login-page`/`login-card`/`login-logo`/`login-tabs`/`login-footer`/`login-agreement`。

## Batch Migration Workflow (10+ pages)

### Phase 1: Read & Map

1. **Read `global.css` first** — understand every available global class.
2. **Read ALL target `.vue` files** — batch-read them.
3. **For each file, build a migration map**:
   - Template classes to replace
   - Scoped styles to remove (duplicate global CSS)
   - Scoped styles to KEEP (unique to page)
   - Special cases: dark pages, tab bars, custom modals

### Phase 2: Write & Strip

4. **Rewrite each file completely** for major template+style overhauls.
5. **For the template layer** — replace all old classes with global equivalents.
6. **For the `scoped` style block** — remove anything covered by global classes.

### Phase 3: Verify

7. **Build** (`npm run build`) to catch CSS class typos.
8. **Browser screenshot** to verify visual consistency.

## Do NOT globalize

- Hero banners (About.vue's gradient hero)
- Dark-theme pages (Download.vue)
- Device list items (Security.vue)
- Swipe-to-delete interactions (Messages.vue)
- Custom modals/dialogs
- Animation keyframes
