# GeoIP 定位修复（中国区）

## 问题

`ip-api.com` 对中国 IP 定位不准，典型表现：青岛用户被识别为济南市。

## 修复方案

后端 `/api/config/geoip`（`config_api.py`）改为使用 `ipinfo.io` + 英→中城市名映射。

### 代码

```python
@config_bp.route('/geoip', methods=['GET'])
def geoip():
    client_ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
    if not client_ip:
        client_ip = request.headers.get('X-Real-IP') or request.remote_addr
    try:
        url = f'https://ipinfo.io/{client_ip}/json?token='
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        r = urllib.request.urlopen(req, timeout=5)
        data = json.loads(r.read())
        city = data.get('city', '') or data.get('region', '') or ''
        city = city.strip()
        # 英→中城市名映射
        city_map = {
            'Beijing': '北京市', 'Shanghai': '上海市', 'Guangzhou': '广州市',
            'Shenzhen': '深圳市', 'Hangzhou': '杭州市', 'Chengdu': '成都市',
            'Qingdao': '青岛市', 'Changsha': '长沙市', 'Wuhan': '武汉市',
            'Nanjing': '南京市', 'Chongqing': '重庆市', 'Xiamen': '厦门市',
            'Dalian': '大连市', 'Kunming': '昆明市', 'Harbin': '哈尔滨市',
            'Suzhou': '苏州市', 'Tianjin': '天津市', 'Jinan': '济南市',
            # ...省略其他城市
        }
        cn_city = city_map.get(city, city)
        return success({'city': cn_city})
    except Exception:
        return success({'city': ''})
```

## 服务对比

| 服务 | 青岛联通 IP | 腾讯云 IP | 特点 |
|------|-----------|----------|------|
| `ip-api.com` (旧) | ❌ 济南市 | ❌ 济南市 | 中国区不准 |
| `ipinfo.io` (新) | ✅ 青岛市 | ⚠️ 北京市(云IP注册地) | 中国区较准 |
| 腾讯位置服务 | ❌ demo key 无 WebserviceAPI | — | 需申请正式 key |

## 注意事项

- `ipinfo.io` 返回英文城市名，需硬编码 `city_map` 转换 → 中文
- 城市映射只覆盖常见城市列表，不在映射表中的返回英文原名
- 云服务器 IP 显示为注册地（如腾讯云北京），这是正常现象
- 备用方案：如需更准可用 GPS 定位（浏览器 `navigator.geolocation`）+ 腾讯地图逆地理编码
