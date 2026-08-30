# 首页配色设计系统

## Hero 渐变区

### 改前：单调紫
```css
background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #5b2c8e 100%);
```

### 改后：蓝粉金（三色渐变 + 流光动画）
```css
background: linear-gradient(135deg, #4158D0 0%, #C850C0 46%, #FFCC70 100%);
animation: heroFlow 8s ease infinite;
background-size: 200% 200%;

@keyframes heroFlow {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
```

### 装饰粒子动画
```css
.hero-bg::after {
  /* 右上大气泡 */
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  animation: floatBubble 6s ease-in-out infinite;
}
.hero-bg::before {
  /* 左下小气泡 */
  background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
  animation: floatBubble2 8s ease-in-out infinite;
}
@keyframes floatBubble {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-30px, 20px) scale(1.1); }
}
@keyframes floatBubble2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(20px, -30px) scale(1.15); }
}
```

## 区块标题 — 渐变文字

```css
.section-title {
  font-size: 17px; font-weight: 700;
  background: linear-gradient(135deg, #4158D0, #C850C0);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

## 游戏卡片 — 白底圆角卡片

```css
.game-item {
  background: #fff;
  border-radius: 14px;
  padding: 10px 0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  cursor: pointer;
  transition: transform 0.2s;
}
.game-item:active { transform: scale(0.95); }
```

## 推荐陪玩师卡片 — 3D 倾斜

```css
.rec-card {
  position: relative;
  border-top: 2px solid rgba(255,255,255,0.8);
  box-shadow: 0 1px 0 rgba(255,255,255,0.6) inset, ...;
  transform: perspective(1000px) rotateX(1.5deg);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}
.rec-card:active {
  transform: perspective(1000px) rotateX(0) translateZ(6px);
}
```

## 陪玩师列表 — 3D 立体

```css
.playmate-item {
  position: relative;
  border-top: 2px solid rgba(255,255,255,0.8);
  box-shadow: 0 1px 0 rgba(255,255,255,0.6) inset, ...;
  transform: perspective(800px) rotateX(1deg);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}
.playmate-item::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 40%;
  background: linear-gradient(180deg, rgba(255,255,255,0.4) 0%, transparent 100%);
  border-radius: 16px 16px 0 0;
  pointer-events: none;
}
```

## Banner 色系

| 项 | 渐变 |
|---|------|
| Banner 1 | `#ff6b6b → #ee5a24`（红橙） |
| Banner 2 | `#667eea → #5b2c8e`（紫） |
| Banner 3 | `#f093fb → #f5576c`（粉红） |

## 快捷入口图标色

| 入口 | 渐变 |
|------|------|
| 全部 | `#667eea → #764ba2`（默认紫） |
| 热门 | `#ffecd2 → #fcb69f`（暖橙） |
| 最新 | `#a1c4fd → #c2e9fb`（蓝白） |
| 大神 | `#ffd700 → #ffb347`（金色） |
| 语音 | `#fbc2eb → #a6c1ee`（紫粉） |
| 女陪玩 | `#f093fb → #f5576c`（粉红） |
