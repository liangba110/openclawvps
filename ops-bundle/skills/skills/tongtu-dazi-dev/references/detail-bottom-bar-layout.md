# Detail Page Bottom Bar Layout Fix

## Problem
Detail page bottom bar (❤️收藏 + 💬聊一聊 + 立即预约) not showing or covered by bottom navigation bar.

## Root Cause Chain
1. Bottom bar was INSIDE `v-if="info"` div — only renders after API loads
2. `z-index: 9999` on bottom bar covered the global bottom nav (z-index: 1000) 
3. Both `position: fixed; bottom: 0` — they overlap

## Final Working CSS
```css
/* Detail.vue bottom-bar */
.bottom-bar {
  position: fixed; bottom: 56px; left: 0; right: 0;
  z-index: 900;  /* BELOW bottom-nav (1000) */
  background: #fff; border-top: 2px solid #667eea;
  padding: 10px 16px;
  display: flex; align-items: center; gap: 12px;
  box-shadow: 0 -4px 16px rgba(0,0,0,0.15);
}

/* Detail.vue spacer */
.bottom-spacer { height: 140px; }  /* room for both bars */

/* App.vue bottom-nav (global) */
.bottom-nav {
  position: fixed; bottom: 0; left: 0; right: 0;
  z-index: 1000;  /* ABOVE detail bar */
  height: 64px;
}
```

## Layout Result
```
┌──────────────────┐
│   Detail content  │
│   spacer 140px    │
├──────────────────┤ ← 预约栏 (bottom:56px, z:900)
│ 🤍  💬  立即预约  │
├──────────────────┤ ← 底部导航 (bottom:0, z:1000)
│ 🏠 发现 订单 我的 │
└──────────────────┘
```

## Also Required
- Bottom bar moved OUTSIDE `v-if="info"` div so it renders independently
- `goChat()` updated to pass `companion_id` and `name` to `/service` page
- `CustomerService.vue` shows "与 xxx 对话" when companion info present
