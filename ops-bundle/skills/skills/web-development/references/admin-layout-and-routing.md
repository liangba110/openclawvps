# Admin Layout CSS Architecture (Vue 3)

## Problem: Global CSS conflicts with scoped CSS in admin panel pages

When admin pages use BOTH global CSS (`global.css`) AND scoped styles, the global CSS applies to ALL page instances. A rule like:

```css
.admin-main { margin-left: 220px; flex: 1; }
```

combined with per-page scoped styles:

```css
.admin-main { flex: 1; padding: 20px; }
```

Results in `margin-left: 220px` from global CSS persisting because scoped styles don't override it (they would need `margin-left: 0` explicitly).

## Fix

Keep layout properties (flex, min-height) in global CSS. Page-specific overrides must explicitly reset inherited properties:

```css
.admin-layout { display: flex; min-height: 100vh; }
.admin-main { flex: 1; min-height: 100vh; }
```

If you remove a property from global CSS, the dist MUST be fully rebuilt (`rm -rf dist node_modules/.vite && npm run build`) because Vite may not detect the change otherwise.

## Verifying CSS changes in compiled output

After rebuilding, ALWAYS verify the change took effect in the compiled dist:

```bash
# Find the compiled CSS file (hash changes each build)
ls dist/assets/style-*.css

# Verify admin-main has no margin-left
python3 -c "
with open('dist/assets/style-*.css', 'rb') as f:
    data = f.read()
idx = data.find(b'admin-main')
if idx >= 0:
    chunk = data[idx:idx+100].decode('utf-8', errors='replace')
    print(chunk)
"
```

The dist CSS file hash changes on every rebuild (e.g., `style-nB2I0pL_.css` → `style-DFERbZao.css`). Always find the new filename before inspecting.

## CSS from "orphaned" lines outside style blocks

When a CSS property ends up on a line OUTSIDE a valid CSS block (e.g., after scoped patch removal that left `  margin-left: 220px;\n}` as standalone text), it causes a **Vite build failure**: `error during build: [vite:vue] /path/AdminConfig.vue:5:1: Unexpected }`.

This is NOT a runtime error — the build fails entirely. The error message may point to a different line than the actual problem. To debug:

```bash
npm run build 2>&1 | grep "error during build" -A5
```

Then check the flagged file around the reported line for orphaned CSS.

## Admin sidebar dynamic path pattern

When admin backend paths rotate daily, use this pattern:

1. In `<script setup>`:
   ```vue
   const adminPath = sessionStorage.getItem('admin_route_path') || 'default-path'
   ```

2. In template:
   ```vue
   <div class="menu-item" :class="{ active: isActive(`/${adminPath}/users`) }"
        @click="$router.push(`/${adminPath}/users`)"`
   ```

3. In router:
   ```js
   export function createAdminRoutes(prefix) {
     const p = `/${prefix}`
     return [
       { path: `${p}/users`, component: ... },
     ]
   }
   ```

4. On app mount, fetch current path and store it:
   ```js
   fetch('/api/admin/path').then(r => r.json()).then(d => {
     const oldPath = sessionStorage.getItem('admin_route_path')
     const newPath = d.data.path
     sessionStorage.setItem('admin_route_path', newPath)
     // Reload if path changed (router was already created with old path)
     if (oldPath && oldPath !== newPath) {
       window.location.reload()
     }
   })
   ```

Never use `sessionStorage` or `localStorage` directly in Vue 3 template expressions. They are not accessible in the template context and calling `.getItem()` on their `undefined` value throws `Cannot read properties of undefined (reading 'getItem')`.

## Browser-based layout debugging

To verify admin layout CSS properties in the browser without manual inspection:

```js
// Run in Playwright or DevTools console
const main = document.querySelector('.admin-main');
const cs = getComputedStyle(main);
console.log({
  marginLeft: cs.marginLeft,
  flex: cs.flex,
  width: main.offsetWidth,
});

// Find which CSS rule applies the margin
for (let i = 0; i < document.styleSheets.length; i++) {
  const sheet = document.styleSheets[i];
  try {
    for (let j = 0; j < (sheet.cssRules || []).length; j++) {
      const rule = sheet.cssRules[j];
      if (rule.style && rule.style.marginLeft === '220px') {
        console.log({ selector: rule.selectorText, file: sheet.href });
      }
    }
  } catch(e) {}
}
```
