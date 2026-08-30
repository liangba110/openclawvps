# Admin Playmate Detail Page — Full Page Audit Pattern

## Problem

The original audit flow used a modal dialog (`v-if="detailVisible"`) with limited data fields. User requested a dedicated full page with ALL companion information.

## Solution

### Route

```js
// router/index.js
{ path: '/admin/playmate/:id', name: 'AdminPlaymateDetail', component: () => import('@/views/admin/AdminPlaymateDetail.vue') }
```

### List page navigation

```js
// AdminPlaymates.vue
function showDetail(pm) {
  router.push(`/admin/playmate/${pm.id}`)  // navigate, don't open modal
}
```

### Detail page structure

1. **Top section:** Avatar (64px circle) + nickname + phone (masked `138****8000`) + audit status badge + [通过]/[拒绝] buttons
2. **基本信息 card:** 3-column grid — phone (masked), city, score, orders, good rate, online status
3. **服务信息 card:** game, rank, 1h/2h/night prices + per-game pricing table (multi-game companions)
4. **个人介绍 card:** `white-space: pre-wrap` for line breaks
5. **标签 card:** flex-wrap chips
6. **生活照 card:** 4-column grid, click to open full-size
7. **审核信息 card:** status, audit_count, audit_fee_paid, registration date

### Phone masking

```js
function maskPhone(p) {
  if (!p) return '-'
  return p.slice(0, 3) + '****' + p.slice(-4)  // 138****8000
}
```

### Data loading

```js
onMounted(async () => {
  const id = route.params.id || route.query.id
  const res = await api.get(`/companion/detail?id=${id}`)
  info.value = res.info || res || {}
})
```

### Life photos handling

```js
const photoUrls = computed(() => {
  const p = info.value.life_photos
  if (!p) return []
  if (Array.isArray(p)) return p
  try { return JSON.parse(p) } catch { return [] }
})

function getPhotoUrl(url) {
  if (!url) return ''
  return url.startsWith('http') ? url : location.origin + (url.startsWith('/') ? url : '/' + url)
}
```
