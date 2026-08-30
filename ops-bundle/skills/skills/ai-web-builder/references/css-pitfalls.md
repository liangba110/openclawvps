# CSS 常见陷阱（aiweb 项目）

## 1. `overflow: hidden` 杀死 `position: sticky`

**现象**: 导航栏设置了 `position: sticky; top: 0` 但滚动时不吸顶。

**根因**: 父元素（或任意祖先）有 `overflow: hidden`。CSS规范规定 `overflow: hidden` 会创建新的滚动容器，sticky 定位只在最近的滚动容器内生效。

**修复**: 移除祖先元素上的 `overflow: hidden`。

**案例**: aiweb 项目中 `#app-root { overflow: hidden }` 导致整个站点的导航栏 sticky 失效。

```css
/* ❌ 错误 */
#app-root { overflow: hidden; }

/* ✅ 正确 */
#app-root {  /* 不设 overflow，或 overflow: visible */ }
```

## 2. 输入框 `transition: all` 导致抖动

**现象**: 页面有后台轮询（如扫码状态轮询每1.5秒）时，输入框持续微微抖动。

**根因**: 
1. 主因：后台轮询定时器（`setInterval`）每1.5秒调用 API → 更新响应式变量 → Vue re-render 整个组件 → 布局微调。切换 Tab 时未清除定时器，轮询在后台持续运行。
2. 次因：`transition: all 0.3s` 让输入框对任何属性变化（包括父容器尺寸变化）都做过渡动画，放大抖动。

**修复**: 
- **清除定时器**：切换 Tab 时 `clearInterval(timer); timer = null`，防止后台轮询触发 re-render
- **transition 精细化**：只过渡需要的属性
- **use `switchToForm()` / `switchToScan()` 管理 tab 切换**：不要直接 `mode = 'form'`，改用函数封装清除/重启定时器逻辑

```css
/* ❌ 错误 — 所有属性都过渡 */
.input { transition: all 0.3s; }

/* ✅ 正确 — 只过渡视觉属性 */
.input { transition: border-color 0.2s, box-shadow 0.2s; }
```

**注意**: `.card` 和 `.btn` 同样不能用 `transition: all`：

```css
/* ❌ 错误 */
.card { transition: all 0.5s cubic-bezier(...); }
.btn { transition: all 0.3s, transform 0.4s; }

/* ✅ 正确 */
.card { transition: border-color 0.3s, box-shadow 0.3s, transform 0.4s; }
.btn { transition: border-color 0.2s, box-shadow 0.2s, transform 0.3s; }
```

## 3. 大面积 CSS 动画导致输入卡顿

**现象**: 页面有大量粒子/轨道/闪烁动画时，输入框输入或页面滚动卡顿。

**根因**: 80+ 粒子元素 + SVG `<animate>` 元素同时运行时，浏览器持续 repaint，主线程被占满。

**修复**: 
- 给动画元素加 `will-change: transform, opacity` 开启 GPU 合成层
- 动画优先使用 `transform` 和 `opacity`（GPU加速属性），避免 `left/top/width/height`
- 在页面容器上加 `isolation: isolate` 隔离前景/背景合成层，防止背景动画的 repaint 影响前景输入框

```css
/* GPU加速动画元素 */
.dot {
  animation: burst linear infinite;
  will-change: transform, opacity;
}

/* 页面层隔离 — 防止背景动画影响前景输入框 */
.page { isolation: isolate; }
.home-page { isolation: isolate; }
```

## 4. `router-link` 被 `::before` 伪元素遮挡

**现象**: Logo（包裹在 `router-link` 内）在 `.page-header` 中有显示但点击无反应。

**根因**: `.page-header::before` 伪元素设置了 `position: absolute; inset: 0; z-index: 0`，覆盖了整个 header 区域。`router-link`（inline 元素）的点击区域被伪元素阻挡。

**修复**: 给 `router-link` 添加 `position: relative; z-index: 2`：

```html
<router-link to="/" style="display:inline-block;text-decoration:none;position:relative;z-index:2">
  <img src="/logo.svg" alt="汇智云" style="height:44px;vertical-align:middle" />
</router-link>
```

注意: `page-header h1, page-header p` 默认有 `z-index: 1`，所以 `router-link` 需要至少 `z-index: 2`。

## 5. 3D 透视页面元素

**关键 CSS**: 3D 卡片效果依赖于 `perspective` + `transform-style: preserve-3d` + `translateZ`。

```css
/* 全局透视 */
#app-root { perspective: 1200px; perspective-origin: 50% 30%; }

/* 卡片3D */
.card {
  transform-style: preserve-3d;
  transform: perspective(1000px) rotateX(0deg) rotateY(0deg);
  transition: all 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}
.card:hover {
  transform: perspective(1000px) rotateX(-3deg) rotateY(1deg) translateY(-6px) scale(1.02);
}

/* 图标浮动突出 */
.card .f-icon { transform: translateZ(25px); }
.card:hover .f-icon { transform: translateZ(50px) scale(1.15); }
```

**注意**: `position: sticky` / `position: fixed` 的元素会脱离 3D 空间，`translateZ` 对其无效。导航栏的3D效果需要用其他方式实现（如阴影、渐变色）。

## 5. logo.svg 权限陷阱

`cp` 或 `rsync` 后的 `.svg` 文件默认权限为 `600`（仅所有者可读），Nginx（`www-data` 用户）无法读取，返回 403。

```bash
# 每次部署后必须：
chmod 644 /var/www/aiweb/frontend/dist/logo.svg
chmod 644 /var/www/aiweb/frontend/dist/favicon.svg

# 并验证：
curl -sk -o /dev/null -w "%{http_code}" https://aiweb.openai2000.cn/logo.svg
# → 期望 200
```

## 6. 生成页面的导航锚点缺失

**现象**: AI生成的网站在预览中导航链接（关于我们、服务项目等）点击后无响应（页面不滚动）。

**根因**: 生成HTML时，导航栏的 `<a href="#about">关于我们</a>` 使用了页面 slug 作为锚点，但 `render_page_header()` 输出的 `<section>` 没有 `id` 属性。浏览器找不到目标锚点。

**修复**: 在 `generate_html()` 中，为每个页面的第一个组件输出的 `<section>` 添加 `id` 属性：

```python
for page in pages:
    page_id = page.get('slug', 'page')
    for i, comp in enumerate(page.get('components', [])):
        r = RENDERERS.get(comp['type'])
        if r:
            comp_html = r(comp['props'])
            if i == 0:  # 第一个组件加id
                comp_html = comp_html.replace('<section', f'<section id="{page_id}"', 1)
            content += comp_html
```

还需在CSS中添加 `scroll-margin-top` 以补偿固定导航栏遮挡：

```css
section { padding: 80px 0; scroll-margin-top: 70px; }
```
