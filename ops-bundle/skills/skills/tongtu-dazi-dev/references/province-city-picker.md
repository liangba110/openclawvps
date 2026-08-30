# 省市二级联动城市选择器

## 场景
搭子列表筛选城市、设置页选择用户所在城市时，需要从18个城市扩展到全国34个省级行政区+300+城市。

## 数据结构

创建 `src/utils/cities.js`：

```javascript
const PROVINCES = [
  {
    name: '广东省',
    cities: ['广州市', '深圳市', '东莞市', '佛山市', ...]
  },
  // ... 34 个省级行政区
]

// 辅助函数
function getAllCities() { /* 扁平列表，用于搜索 */ }
function findProvince(cityName) { /* 根据城市找省份 */ }
function searchCities(keyword) { /* 模糊搜索 */ }

export default PROVINCES
export { getAllCities, findProvince, searchCities }
```

## 模板实现（List.vue 示例）

### 弹窗结构
```html
<div class="city-picker" v-if="showCityPicker" @click.self="closeCityPicker">
  <div class="cp-box">
    <div class="cp-title">
      <span v-if="selectedProvince" class="cp-back" @click="selectedProvince = ''">‹ 返回</span>
      <span>{{ selectedProvince ? selectedProvince : '选择省份' }}</span>
    </div>
    <!-- 省份列表 -->
    <template v-if="!selectedProvince">
      <div class="cp-item" @click="selectCity('')">全部城市</div>
      <div class="cp-item" v-for="p in provinces" :key="p.name"
            @click="selectedProvince = p.name">
        <span>{{ p.name }}</span>
        <span class="cp-arrow">›</span>
      </div>
    </template>
    <!-- 城市列表 -->
    <template v-else>
      <div class="cp-item" v-for="c in currentCities" :key="c"
            :class="{ active: selectedCity === c }"
            @click="selectCity(c)">{{ c }}</div>
    </template>
  </div>
</div>
```

### Script 部分
```javascript
import PROVINCES from '@/utils/cities'

const provinces = ref(PROVINCES)
const selectedProvince = ref('')

const currentCities = computed(() => {
  if (!selectedProvince.value) return []
  const p = provinces.value.find(p => p.name === selectedProvince.value)
  return p ? p.cities : []
})

function selectCity(c) {
  selectedCity.value = c
  selectedProvince.value = ''
  showCityPicker.value = false
  // 触发筛选
}

function closeCityPicker() {
  showCityPicker.value = false
  selectedProvince.value = ''
}
```

### CSS 关键
```css
.cp-box { background:#fff; border-radius:16px; padding:20px; width:300px; max-height:70vh; overflow-y:auto; }
.cp-title { font-size:16px; font-weight:700; text-align:center; margin-bottom:10px; position:relative; }
.cp-back { position:absolute; left:0; top:0; font-size:16px; color:#667eea; cursor:pointer; }
.cp-item { padding:10px; text-align:center; border-radius:8px; cursor:pointer; font-size:14px; display:flex; justify-content:space-between; }
.cp-item:hover,.cp-item.active { background:#f0f2ff; color:#667eea; }
.cp-arrow { font-size:14px; color:#ccc; }
```

## Settings.vue 的特殊处理

设置页需要搜索功能（在省级内搜索城市）：

```html
<template v-if="settingProvince">
  <div class="cp-search">
    <input v-model="citySearch" placeholder="搜索城市..." class="cp-input" />
  </div>
  <div class="cp-list">
    <div class="cp-item" v-for="c in filteredCities" :key="c"
         :class="{ active: userCity === c }"
         @click="selectCity(c)">{{ c }}</div>
    <div v-if="filteredCities.length === 0" class="cp-empty">未找到匹配城市</div>
  </div>
</template>
```

## 旧版清理
替换后必须 grep 确认无 `CITY_LIST` / `cityList` 残留：
```bash
grep -rn "CITY_LIST\|cityList" src/views/
# 期望: 0 行
```
