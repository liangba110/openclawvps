---
name: ui-ux-pro-max
description: UI/UX design intelligence and implementation guidance for building polished interfaces. Use when the user asks for UI design, UX flows, information architecture, visual style direction, design systems/tokens, component specs, copy/microcopy, accessibility, or to generate/critique/refine frontend UI (HTML/CSS/JS, React, Next.js, Vue, Svelte, Tailwind). Includes workflows for (1) generating new UI layouts and styling, (2) improving existing UI/UX, (3) producing design-system tokens and component guidelines, and (4) turning UX recommendations into concrete code changes.
---

Follow these steps to deliver high-quality UI/UX output with minimal back-and-forth.

## 1) Triage
Ask only what you must to avoid wrong work:
- Target platform: web / iOS / Android / desktop
- Stack (if code changes): React/Next/Vue/Svelte, CSS/Tailwind, component library
- Goal and constraints: conversion, speed, brand vibe, accessibility level (WCAG AA?)
- What you have: screenshot, Figma, repo, URL, user journey

If the user says "全部都要" (design + UX + code + design system), treat it as four deliverables and ship in that order.

## 2) Produce Deliverables (pick what fits)
Always be concrete: name components, states, spacing, typography, and interactions.

- **UI concept + layout**: Provide a clear visual direction, grid, typography, color system, key screens/sections.
- **UX flow**: Map the user journey, critical paths, error/empty/loading states, edge cases.
- **Design system**: Tokens (color/typography/spacing/radius/shadow), component rules, accessibility notes.
- **Implementation plan**: Exact file-level edits, component breakdown, and acceptance criteria.

## Deliverables

### Logo / Brand Design Iteration Workflow

When designing logos, icons, or brand assets for a Chinese web project:

1. **Never overwrite production files directly** — always create a preview page first
2. **Create a preview HTML** showing all variants side-by-side with usage descriptions
3. **Serve via HTTP** (e.g. Caddy web root or static file server) and share the URL
4. **Iterate based on feedback** before touching any production code
5. **Only deploy to the live site after explicit user approval**
6. **Fix file permissions after every SVG copy**: `sudo chmod 644 *.svg`. SVG files copied with `cp` may retain 600 permissions, causing Nginx 403 errors.

Logo design conventions for Chinese tech/AI brands:
- Use blue-purple gradients (#2563EB → #7C3AED is a common AI-industry palette)
- Cloud + AI mark is the standard icon motif; **this user prefers no rounded-square background** (just the cloud shape floating, no container box)
- **This user prefers wordmark-only** — brand name without subtitle. Domain text below the name was also rejected.
- Clean sans-serif Chinese typography (Microsoft YaHei, PingFang SC), 500-600 weight, 24-30px for nav logos
- Provide at minimum 6 variants: horizontal (nav bar), square (app icon), favicon (browser tab), dark-mode, badge (small stamp), social share (1200×630)
- SVG is preferred format (scales perfectly, small file size, no resolution issues)

**SVG centering math for horizontal logos:**
When a viewBox="0 0 W H" logo has both an icon and text:
1. Calculate icon's full span: `iconLeft` to `iconLeft + iconWidth`
2. Calculate text's full span: `textLeft` to `textLeft + textWidth` (3 chars at 26px ≈ 78px)
3. Total content center = `(iconLeft + textLeft + textWidth) / 2`
4. Adjust so total center equals `W/2` (the viewBox horizontal center)
5. Same logic vertically using y-coordinates and heights
For a typical 200×52 viewBox: icon(~60px) + gap(12px) + text(~78px) = 150px → left padding = (200-150)/2 = 25px

**Common user feedback patterns (this user):**
- "太小了" → increase element size by 30-50%, not incrementally
- "没居中" → recalculate SVG coordinates precisely
- "看不清" → enlarge font, increase icon scale
- "去掉XX" → listen to which element specifically and remove it entirely
- "不好看了" → roll back the last change immediately
- Always deploy a preview URL first and wait for confirmation before touching production

## 3) Use Bundled Assets
This skill bundles data you can cite for inspiration/standards.

- **Design intelligence data**: Read from `skills/ui-ux-pro-max/assets/data/` when you need palettes, patterns, or UI/UX heuristics.
- **Upstream reference**: If you need more phrasing/examples, consult `skills/ui-ux-pro-max/references/upstream-skill-content.md`.

## 4) Optional Script (Design System Generator)
If you need to quickly generate tokens and page-specific overrides, use the bundled script:

```bash
python3 skills/ui-ux-pro-max/scripts/design_system.py --help
```

Prefer running it when the user wants a structured token output (ASCII-friendly).

## CSS Space / Tech Theme Animation Patterns

Use these for Chinese tech/AI SaaS platforms. Elements layer on a fixed background without affecting page scroll.

### 1. Background Layer Stack (z-index -3 to -1)
```
#app-root { z-index: 0; }           /* content */
.bg-gradient (z-index: -3)          /* animated gradient */
.bg-grid (z-index: -2)              /* scrolling grid */
.bg-orb / .orbit (z-index: -1)     /* floating decorations */
```
**WARNING**: Never `overflow: hidden` on `#app-root` — it breaks `position: sticky` on nav bars.

### 2. Particle Systems (Vue v-for)
**Burst from center** (80 particles):
```css
.dot { left: 50%; top: 50%; }
@keyframes burst {
  0%   { transform: translate(0,0) scale(0); opacity: 0; }
  15%  { transform: translate(calc(var(--x)*0.2), calc(var(--y)*0.2)) scale(1); }
  100% { transform: translate(var(--x), var(--y)) scale(0); }
}
/* CRITICAL: every keyframe needs translate() — omitting resets to (0,0) */
```
**Rising particles**: `position: absolute; top: 100%;` → `translateY(-120vh)`.

### 3. Orbiting Rings (纯CSS)
```css
.orbit { border: 1.5px solid rgba(X); animation: orbitSpin 12s linear infinite; }
.orbit::before { /* glowing dot */ }
@keyframes orbitSpin { 0% { rotate: 0deg; } 100% { rotate: 360deg; } }
```

### 4. SVG Network Lines
```xml
<line stroke="rgba(59,130,246,0.25)" stroke-linecap="round">
  <animate attributeName="stroke-opacity" values="0.25;0.5;0.25" dur="3s" .../>
</line>
```
Add pulsing nodes + travelling dots (animated `cx`/`cy`).

### 5. CSS 3D Card Depth
```css
.card { transform-style: preserve-3d; backface-visibility: hidden; }
.card:hover { transform: perspective(1000px) rotateX(-3deg) translateY(-6px) scale(1.02); }
.card .f-icon { transform: translateZ(25px); }
.card:hover .f-icon { transform: translateZ(50px) scale(1.15); }
.card h3 { transform: translateZ(15px); } .card p { transform: translateZ(5px); }
```

### 6. Navigation Bar (Chinese Tech Sites)
- **Black nav** (`#0d0d0d`): Use `logo-dark.svg` or `filter: brightness(0) invert(1)` on logo
- **White glass nav**: `rgba(255,255,255,0.92)`. Add bottom blue glow `::after`.
- **Sticky**: `position: sticky; top: 0; z-index: 100;` — parent must NOT have `overflow: hidden`
- **Buttons**: This user prefers same gradient style for ALL buttons (both login & register blue)
- **Height**: `padding: 18-20px` vertical

### 7. Color Iteration Workflow (this user)
1. Start blue-white space theme (#d0e2ff-#e8f0fe gradient, white cards)
2. Darken ~20% per iteration if rejected
3. "不行还是上一个颜色吧" → revert immediately
4. "看不清" → increase opacity 2-3x (not 20-30%)
5. Nav: eventually settled on black + blue gradient buttons

## Output Standards
- Default to ASCII-only tokens/variables unless the project already uses Unicode.
- Include: spacing scale, type scale, 2-3 font pair options, color tokens, component states.
- Always cover: empty/loading/error, keyboard navigation, focus states, contrast.
