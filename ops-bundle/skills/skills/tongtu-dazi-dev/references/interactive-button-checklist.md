# Interactive Button Checklist

When adding or debugging buttons (order, favorite, share, chat) on any page:

## 1. Token Check for Authenticated Actions

Any button that calls an authenticated API MUST check for token FIRST. No silent failure:

```js
function goOrder() {
  if (!localStorage.getItem('token')) {
    safeToast('请先登录'); router.push('/login'); return
  }
  router.push(...)
}
```

## 2. @click.stop on List Item Buttons

When adding buttons inside a list item with a parent click handler:
```html
<div class="list-item" @click="goDetail(item.id)">
  <div class="list-actions" @click.stop>  <!-- 👈 prevents card click -->
    <button @click="toggleFav(item)">🤍</button>
    <button @click="goOrder(item)">预约</button>
  </div>
</div>
```

## 3. Template @click Must Match Function Name (Silent Bug!)

When renaming a function, template `@click` binding MUST be updated. Vue 3 does NOT throw errors for undefined handlers — button silently does nothing.

**Check after refactoring:**
```bash
grep -oP '@click="\K[^"]+' Detail.vue | while read fn; do
  grep -q "function $fn\b" Detail.vue || echo "⚠️ MISSING: $fn"
done
```

**Real case:** `sharePlaymate` renamed to `shareProfile` in script but template still had `@click="sharePlaymate"` → "⋯" button did nothing for multiple deploys before detection.

## 4. Clipboard Requires HTTPS — HTTP Fallback

`navigator.clipboard?.writeText()` is `undefined` on HTTP → crashes with `TypeError: Cannot read properties of undefined (reading 'writeText')`.

**Fix — textarea fallback:**
```js
function copyLink(url) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).then(...)
  } else {
    const ta = document.createElement('textarea')
    ta.value = url; ta.style.position = 'fixed'; ta.style.left = '-9999px'
    document.body.appendChild(ta); ta.select()
    document.execCommand('copy'); document.body.removeChild(ta)
  }
}
```

## 5. navigator.share Requires HTTPS Too

```js
function shareProfile() {
  const url = window.location.href
  if (navigator.share) {
    navigator.share({ title, text, url }).catch(() => copyLink())
  } else {
    copyLink()
  }
}
```

## 6. goOrder Must Handle Multi-Game Companions

```js
function goOrder() {
  const gid = (info.value.games && info.value.games[0])
    ? info.value.games[0].id
    : info.value.game_id
  router.push({ path: '/order/create', query: { companion_id, game_id: gid, service_type } })
}
```

## 7. goChat Should Pass Companion Info

When "聊一聊" is clicked on detail page:
```js
router.push({ path: '/service', query: { companion_id, name: info.value.nickname } })
```
CustomerService reads `route.query` → displays "与 xxx 对话", hides FAQ panel.

## 8. Method Mismatch — 405 POST vs GET

Backend route `methods=['GET']` but frontend calls `api.post()`:
```js
// ❌ 405 Method Not Allowed
api.post('/favorite/check', { companion_id })

// ✅ Correct
api.get('/favorite/check', { params: { companion_id } })
```

## 9. Data Unwrap — `res.list` not `res`

List APIs return `{list: [], total: N}`. Axios interceptor unwraps to `{list:[], total:N}` — an object, NOT array:
```js
// ❌ .map is not a function
allOrders.value = (res || []).map(...)

// ✅ Access .list first
allOrders.value = ((res && res.list) || []).map(...)
```

## 10. Confirm Dialog — Use Vant showConfirmDialog, NOT browser confirm()

Browser `confirm()` is blocked on many mobile WebViews:
```js
import { showConfirmDialog } from 'vant'
showConfirmDialog({ title: '确认', message: '确认支付？' }).then(...).catch(...)
```

## 11. `setInterval` Returns Number — Can't Attach Properties

```js
// ❌ TypeError: Cannot create property '_slow' on number
let timer = setInterval(...)
timer._slow = setInterval(...)  // number primitives can't have properties

// ✅ Separate variables
let timer = null, slowTimer = null
```

## 12. Phone Masking

```js
function maskPhone(p) {
  if (!p) return '-'
  return p.slice(0, 3) + '****' + p.slice(-4)
}
// "13800138000" → "138****8000"
```

## 13. Save City — Use PUT /user/update, NOT POST /user/profile

`api.put('/user/update', { city })` — the user update endpoint is PUT, not POST.

## 14. Avatar URL Must Be Absolute, Not Relative

Backend often returns avatar as relative path like `/avatars/boy3.jpg`. On a different origin (or reverse proxy path) this 404s.

```js
// ❌ Relative path 404s when served under a different mount point
avatar.value = info.avatar

// ✅ Prefix origin
let av = info.avatar || ''
if (av && av.startsWith('/') && !av.startsWith('//')) {
  av = window.location.origin + av
}
avatar.value = av
```

**isEmoji() helper for displaying emoji vs image:**
```js
function isEmoji(s) {
  if (!s) return false
  // URLs (containing /, ., or http://) are not emojis
  if (s.startsWith('http') || s.includes('.') || s.includes('/')) return false
  return true
}
```

**Template:**
```html
<div class="avatar-box" v-if="avatar && !isEmoji(avatar)">
  <img :src="avatar" @error="avatar=''" />
</div>
<div class="avatar-box" v-else>{{ avatar || '🎮' }}</div>
```

## 15. Nginx Has TWO `location /uploads/` Blocks — Silent Avatar 404

**Problem:** Server B hosts multiple sites (port 80 ttdazi + port 5003 huizhiyun). Each defines its own `location /uploads/` block. The first one to match wins. If the wrong block aliases to a non-existent path, ALL uploads return 404 even though files exist on Server A.

**Diagnosis:**
```bash
ssh ubuntu@82.157.202.24 "sudo nginx -T 2>/dev/null | grep -n 'location /uploads/'"
# Output:
# 222:    location /uploads/ {        ← BAD: alias /var/www/uploads/
# 303:    location /uploads/ {        ← GOOD: proxy_pass http://backend
```

**Fix — delete the wrong alias config:**
```bash
ssh ubuntu@82.157.202.24 "sudo sed -i '/alias \\/var\\/www\\/uploads\\/;/d' /etc/nginx/sites-enabled/ttdazi && sudo nginx -t && sudo nginx -s reload"
```

**Verify:** `curl -sI http://host/uploads/avatars/user_xxx.jpg | head -1` → `HTTP/1.1 200 OK`

**Why it happens:** When adding apps behind one Nginx, duplicate `location` blocks silently override each other. First match wins regardless of file order. Always audit `nginx -T` after adding a new app.

## 16. Orphan Avatar Path in DB — Reset to Default

**Problem:** Avatar upload flow saved the new avatar URL to DB before file write succeeded, OR file was deleted but DB still has the path → 404 loop on every page load.

**Fix — reset DB path to default emoji:**
```sql
UPDATE user SET avatar='🐱' WHERE id=10027;
```

## 17. TDZ Trap When Patching Multiple Files with Same Helper

When adding the same helper (e.g. `isEmoji()`, `refreshCaptcha()`) to Login.vue, Register.vue, EmailRegister.vue, FollowRegister.vue — patch them all in one pass. Regex escape errors in `execute_code` can produce THREE copies of the function declaration if you re-run, OR truncate the function body (e.g. `s.inclth('http')` instead of `s.includes('http')`). Always rebuild after patching and check `grep -c 'function X' file.vue` matches the expected count (should be 1).