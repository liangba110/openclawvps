# 同途搭子 Logo 设计迭代流程

## 设计方法论

当用户要求设计/重设计网站 logo 时，按以下多轮迭代进行：

1. **V1 — 发散探索**：出 4 个不同方向方案（字母标/图形标/组合标/品牌全称）
2. **V2 — 转向调整**：若用户否定全部，出 4 个全新方向（人际/对话/飘带/皇冠等）
3. **V3 — 深入参考**：若用户指定风格（如"比心"），按该风格出 6 个变体
4. **V4+ — 精化方向**：选中方向后出 9 个演绎方案
5. **科技升级**：要求"高端/大气/科技"时，转向棱镜/轨道/无限/钻石/全息风格

## 设计稿输出方式

每轮输出独立的 HTML 文件（`/tmp/logo_vN.html`），用 `npx playwright screenshot` 截图后通过 `MEDIA:` 发给用户。

```bash
# 启动本地 HTTP 服务截图
cd /tmp && python3 -m http.server 8999 &
npx playwright screenshot "http://127.0.0.1:8999/logo_vN.html" /tmp/logo_vN.png --full-page
```

## V3 最终确认版

用户最终选定的 V3 风格——紫色渐变方块 + 🎮 emoji + 品牌名 + 拼音：
- 配色：`linear-gradient(135deg, #667eea, #764ba2)`
- 图标：🎮 emoji（不要用 H/TT 等字母，不要用 SVG 图形）
- 品牌字体：`font-weight: 800; letter-spacing: 4-5px`

## 全套 SVG 生成与替换

### favicon
```svg
<svg width="48" height="48" viewBox="0 0 48 48">
  <rect width="48" height="48" rx="12" fill="url(#g)"/>
  <text x="24" y="34" text-anchor="middle" font-size="26">🎮</text>
</svg>
```
viewBox 48×48, rx=12, font-size=26。不要用 100×100 viewBox（会裁剪）。

### 其他版本

| 文件 | 用途 | 关键尺寸 |
|------|------|---------|
| `logo-vertical.svg` | 竖版主Logo | 🎮 方块 120×120 rx28 + 品牌字 y=180 28px + 拼音 y=210 12px |
| `logo-horizontal.svg` | 横版Header | 🎮 方块 56×56 rx14 + 品牌字 y=48 26px |
| `logo-app.svg` | App图标 | 🎮 方块 180×180 rx40 + 🎮 60px + 品牌字 14px |
| `logo-wechat.svg` | 圆形头像 | 圆 120×120 + 🎮 38px + 品牌字 12px |

### 品牌字使用 `-webkit-background-clip: text` 渐变

文字不写死在 SVG 中为纯色，应用 CSS gradient text：
```css
background: linear-gradient(135deg, #667eea, #764ba2);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
background-clip: text;
```

## 替换流程

```bash
# 1. 创建 favicon.svg（/opt/ttdazi/frontend/public/）
# 2. 创建全套 logo SVG（/opt/ttdazi/frontend/public/logo/）
# 3. 更新 index.html favicon 链接
# 4. 更新 Download.vue 文件列表
# 5. 构建部署
cd /opt/ttdazi/frontend && npm run build && bash /opt/ttdazi/deploy.sh
```

下载地址：http://82.157.202.24/#/download → 输入密码 → 下载 `ttdazi_logos_v3.zip`
