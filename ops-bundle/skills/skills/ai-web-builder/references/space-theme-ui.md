# 汇智云AI建站 - 太空星系主题UI实现

## 最终视觉方案

蓝白太空星系风 — 蓝紫渐变星球 + 星座连接线 + 繁星 + 扩散粒子 + 3D卡片 + 动态科技感。

## 配色方案

| 用途 | 颜色 | 说明 |
|:----|:----|:------|
| 导航栏背景 | `#0d0d0d` (纯黑) | 与浅色页面内容形成强对比 |
| 页面背景 | `linear-gradient(170deg, #d0e2ff 0%, #e0ecff 30%, #e8f0fe 60%, #dce5f5 100%)` | 蓝白渐变 |
| 主色 | `#0052D9` / `#3B82F6` | 腾讯云蓝风格 |
| 卡片 | `rgba(255,255,255,0.85)` | 半透明白色毛玻璃 |
| 文字 | `#1e293b` / `#475569` | 深灰保证可读性 |
| 品牌Slogan | `汇智云 — 零代码AI智能建站_商城/官网/小程序云端搭建服务商` | |
| SEO标题 | `汇智云AI建站 — 零代码生成官网/商城/小程序 \| AI智能建站平台` | |

## 后台装饰元素

全部放在 `App.vue` 的固定定位层（z-index -3 到 -1），不影响页面内容：

1. **动态渐变背景**: `bg-gradient` — linear-gradient 170度，4色过渡
2. **滚动科技网格**: `space-grid` — `background-size: 50px 50px` + `animation: gridScroll`
3. **3个轨道环**: `orbit o1/o2/o3` — 纯CSS旋转环，各有不同颜色的卫星发光点
4. **SVG科技网络线**: `space-lines` — 实线连接9个节点，3个流动光点沿路径移动
5. **15颗繁星**: `space-stars` — 多层radial-gradient，呼吸闪烁
6. **80个扩散粒子**: `space-dots` — Vue v-for从中心随机方向burst扩散

## 导航栏（黑色）

```css
.nav { background: #0d0d0d; border-bottom: 1px solid rgba(255,255,255,0.06); }
.nav-right .btn { border-radius: 8px; font-weight: 600; }
.nav-right .btn-primary,
.nav-right .btn-secondary { background: linear-gradient(135deg, #0052D9, #2563EB); }
```

导航栏**所有按钮统一蓝渐变样式**（登录和注册按钮使用完全相同的蓝渐变，不再区分 primary/secondary 视觉样式）:
```css
.nav-right .btn-primary,
.nav-right .btn-secondary { background: linear-gradient(135deg, #0052D9, #2563EB); color: #fff; box-shadow: 0 4px 12px rgba(0,82,217,0.2); }
```

Logo使用 `logo-dark.svg`（白字+紫渐变云朵），或者用CSS滤镜：
```css
.nav .logo img { filter: brightness(0) invert(1); }
```

## 3D 卡片效果（style.css）

```css
.card { transform-style: preserve-3d; backface-visibility: hidden; }
.card:hover { transform: perspective(1000px) rotateX(-3deg) rotateY(1deg) translateY(-6px) scale(1.02); }
.card .f-icon { transform: translateZ(25px); transition: transform 0.5s; }
.card:hover .f-icon { transform: translateZ(50px) scale(1.15); }
```

## 页面级配色区分

不同页面使用不同顶边颜色：

| 页面 | 顶边效果 |
|:----|:---------|
| 登录页 | 蓝色渐变头 + 卡片顶部3px蓝色边 |
| 注册页 | 青色渐变头 + 卡片顶部3px青色边 |
| Dashboard | 白色卡片 + 蓝色站点名 |
| 首页板块 | 特色区(白色半透明55%)、行业区(淡蓝底45% rgba(219,234,254,0.45))、流程区(浅白半透明35%)、页脚(白底50%+蓝色顶边) |

## 用户迭代偏好总结

1. 所有视觉元素必须"能看到" — 透明度不足会被批评
2. 导航栏必须固定顶部（sticky），不被滚动遮挡
3. 按钮样式统一（不要区分primary/secondary样式）
4. 深色背景下Logo必须清晰（提供深色版或CSS反白）
5. 颜色调深/调浅迭代时，用户会明确说"不行还是上一个" — 立即回退
