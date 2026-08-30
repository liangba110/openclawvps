# Session Implementation Notes: 2026-07-14

## Travel Companion Feature Integration

### Database Setup
- Travel categories added to `game` table (IDs 8-14)
- Sensitive words added with types: `block`(23), `warn`(12), `profile_block`(8), `travel`(21)
- 6 travel companion accounts created (青岛向导小张, 成都美食通, 丽江旅拍, 西安历史文化, 杭州徒步向导, 三亚自驾领队)

### Frontend Integration

| File | Change |
|------|--------|
| `Home.vue` | Added dual entry cards (游戏搭子 + 旅游搭子) before 热门搭子 section |
| `List.vue` | Accepts `?type=travel` query param, filters categories by game_id range |
| `Detail.vue` | Shared with game companions, displays travel service types when applicable |
| `CustomerService.vue` | Compliance popup on chat entry (3s delay before closeable) |
| `Agreement.vue` | Updated rules with prohibited behaviors and customer service script |

### Backend API
- `/api/companion/list?type=travel` filters by game_id >= 8
- `/api/companion/list?type=game` filters by game_id < 8

### API Response Pattern
`companion/detail` returns `{data: {info: {...}}}`. Always use:
```javascript
const detail = r?.info || r
```

### Payment Flow
- Payment: `pay.openai2000.cn/pay` → WeChat Pay → confirm → redirect
- Never use XHR POST for callbacks; use Image beacon GET or server-side query
- Confirm endpoint `/api/pay/wxpay/confirm` queries WeChat API directly

### CSS Gotchas
- `position: fixed` bars inside scoped Vue components must be inside the root element
- Bottom bar must have `bottom: 64px` (app nav height) to avoid overlap
- WeChat browser: add `-webkit-transform: translateZ(0)` for fixed positioning
- Fragment root elements don't get scoped styles for siblings

### Price Removal
- All user-facing price displays removed from Home.vue, List.vue, Favorites.vue
- Backend still returns price fields (kept for admin/management)
- Companion's own price settings page (`PlaymateProfile.vue`) kept as-is
