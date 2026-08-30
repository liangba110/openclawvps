# 城市选择器实现（Settings.vue）

## 背景

旧方案使用 `navigator.geolocation` GPS 定位 + `/api/config/geoip` IP 定位（`ip-api.com` / `ipinfo.io`），但因中国 IP 数据库不准确，青岛用户经常被定位为济南或嘉兴，用户体验差。

## 方案

改为**城市选择器弹窗**：用户点击城市行 → 弹窗显示城市列表 → 点击选择 → 保存到 `user.city`。

## 改动的关键文件

| 文件 | 改动 |
|------|------|
| `frontend/src/views/Settings.vue` | 删除 GPS/IP 定位代码，改为城市选择器 |
| `backend/app/config_api.py` | geoip 端点保留但不再依赖（备用） |

## 已删除的代码

- `const locating = ref(false)` — 不再需要
- `async function getLocation()` — GPS + IP 双级定位
- `async function reverseGeo(lat, lng)` — Nominatim 逆地理编码
- CSS 中的 `.loc-btn:disabled`、旧的 `.city-edit` 样式

## 城市列表

硬编码在 `CITY_LIST` 常量中，包含全国 60+ 个地级市。支持按关键词搜索（`filteredCities` computed）。

## 与外部的交互

- 用户选择城市后写入 `user.city`
- 搭子列表页（List.vue）的「同城」筛选从 `localStorage.getItem('user').city` 读取
- 搭子详情页展示 `user.city`

## 注意事项

- 腾讯位置服务 demo key `OB4BZ-D4W3U-B7VVO-4PJWW-6TKDJ-WPB77` 不支持 WebserviceAPI 调用（仅支持浏览器端 JS API），不能用于服务器端反向地理编码
- `ip-api.com` 对中国 IP 定位偏差严重（青岛→济南），`ipinfo.io` 部分 IP 也偏差（青岛→嘉兴），均不可靠
