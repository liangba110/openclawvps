# 省市联动城市选择器实现记录

## 改动范围（2026-07-27）

### 新增文件
- `frontend/src/utils/cities.js` — 34个省级行政区 + 300+城市数据，导出 PROVINCES、getAllCities()、searchCities()

### 修改文件
1. **Home.vue** — 问候语旁添加「📍 定位城市」badge → 省市二级联动picker → 保存到localStorage + API同步
2. **List.vue** — 城市筛选弹窗改为省市二级联动；"同城"按钮无城市时自动弹出picker
3. **Settings.vue** — 城市选择器改为省份→城市 + 搜索

## 城市列表覆盖范围

| 省/直辖市 | 城市数 | 代表城市 |
|-----------|:------:|---------|
| 北京市/上海市/天津市/重庆市 | 区级 | 各区 |
| 广东省 | 21 | 广州、深圳、东莞、佛山、珠海... |
| 浙江省 | 12 | 杭州、宁波、温州、义乌... |
| 江苏省 | 14 | 南京、苏州、无锡、常州... |
| 山东省 | 16 | 青岛、济南、烟台、威海... |
| 四川省 | 19 | 成都、绵阳、德阳、宜宾... |
| 湖北省 | 14 | 武汉、宜昌、襄阳、荆州... |
| 湖南省 | 14 | 长沙、衡阳、株洲、湘潭... |
| 河南省 | 17 | 郑州、洛阳、开封、南阳... |
| +25省/自治区 | 100+ | 覆盖全部主要城市 |

## 部署检查命令

```bash
# 检查生产环境是否有新代码
ssh ubuntu@82.157.202.24 "grep -c '选择省份' /home/ubuntu/ttdazi-frontend/assets/Home-*.js"

# 清理旧chunk
ssh ubuntu@82.157.202.24 "cd /home/ubuntu/ttdazi-frontend/assets && ls -la *.js | grep -v cities- | sort"

# 确认只有最新的chunk存在
ssh ubuntu@82.157.202.24 "ls -la /home/ubuntu/ttdazi-frontend/assets/cities-*.js"
```
