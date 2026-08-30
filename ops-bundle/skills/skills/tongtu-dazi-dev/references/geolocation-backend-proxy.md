# Geolocation: GPS + Backend IP Proxy (CORS-Free)

## Problem

1. `navigator.geolocation.getCurrentPosition()` blocked on HTTP origins in browsers
2. `navigator.clipboard.writeText()` blocked on HTTP — use textarea fallback
3. IP geolocation APIs (ipapi.co, ip.sb) have CORS restrictions from HTTP origins → blocked
4. **CRITICAL:** Direct server-side IP lookup uses server's own IP, NOT the client's → returns server city (Beijing) for all users. Fix: read `X-Forwarded-For` from Nginx proxy headers.

## Failed APIs (do not retry)

| API | Failure |
|-----|---------|
| `ipapi.co/json/` | CORS blocked, 403 |
| `api.ip.sb/geoip` | Returns empty on cloud VMs |
| `ip138.com/iplookup.php` | Returns HTML, not JSON |

## Working: ip-api.com with Client IP from X-Forwarded-For

### Backend proxy (`config_api.py`)

```python
@config_bp.route('/geoip', methods=['GET'])
def geoip():
    import urllib.request, json as j
    # ⚠️ MUST read client IP from Nginx proxy headers
    client_ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if not client_ip:
        client_ip = request.headers.get('X-Real-IP') or request.remote_addr
    try:
        url = f'http://ip-api.com/json/{client_ip}?lang=zh-CN&fields=city,regionName'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        r = urllib.request.urlopen(req, timeout=5)
        data = j.loads(r.read())
        city = data.get('city') or data.get('regionName') or ''
        return success({'city': city})
    except:
        return success({'city': ''})
```

### Verification

```bash
# Simulate Qingdao user (Shandong IP)
curl -s "http://82.157.202.24/api/config/geoip" -H "X-Forwarded-For: 112.224.190.1"
# → {"code":0,"data":{"city":"济南市"},"msg":"success"}

# Without header → server's own IP → Beijing
curl -s "http://82.157.202.24/api/config/geoip"
# → {"code":0,"data":{"city":"北京"},"msg":"success"}
```

### Frontend (Settings.vue)

```js
const locating = ref(false)
const userCity = ref('')

function updateCity() {
  if (userCity.value) api.put('/user/update', { city: userCity.value })
    .then(() => updateLocal({ city: userCity.value }))
}

async function getLocation() {
  locating.value = true
  // Channel 1: Browser GPS (more accurate, blocked on HTTP)
  if (navigator.geolocation) {
    try {
      const pos = await new Promise((res, rej) =>
        navigator.geolocation.getCurrentPosition(res, rej, { timeout: 5000 }))
      const city = await reverseGeo(pos.coords.latitude, pos.coords.longitude)
      if (city) { userCity.value = city; updateCity(); locating.value = false; return }
    } catch {}
  }
  // Channel 2: Backend proxy (works on HTTP, uses client IP)
  try {
    const r = await api.get('/config/geoip')
    if (r.city) { userCity.value = r.city; updateCity(); safeToast('已获取：' + r.city) }
    else safeToast('未识别到城市')
  } catch { safeToast('定位失败，请手动输入城市') }
  locating.value = false
}
```

## City Field in Settings (Not Profile)

User preference: City goes in 设置 → 账号信息, not Profile main page.

Template:
```html
<div class="s-item">
  <span>城市</span>
  <span class="s-val">
    <input v-model="userCity" class="city-inp" placeholder="点击获取或输入" @blur="updateCity" />
    <button class="loc-btn-sm" @click="getLocation" :disabled="locating">定位</button>
  </span>
</div>
```

Sync on mount:
```js
onMounted(() => { userCity.value = user.value.city || '' })
watch(user, v => { userCity.value = v.city || '' })
```
