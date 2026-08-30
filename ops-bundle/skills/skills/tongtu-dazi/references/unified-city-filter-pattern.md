# 城市选择 + 同城过滤统一模式

## 背景

同途搭子平台新增排序栏（综合/同城/好评/人气/📍城市），用户期望在所有列表页面（搭子列表、需求大厅）通过「同城」按钮按所在城市过滤数据。

## 核心状态变量

只用两个 ref，不要混用多个城市变量：

```javascript
const sameCity = ref(false)    // 是否启用同城过滤
const myCity = ref('')         // 当前用户所在城市
const cityName = computed(() => (sameCity.value && myCity.value) ? myCity.value : '城市')
```

❌ 不要同时维护 `selectedCity`、`userCity`、`myCity` 等多个冗余变量。

## 页面加载初始化

```javascript
onMounted(() => {
  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    if (user.city) myCity.value = user.city
  } catch {}
  // ... 后续加载数据
})
```

从 localStorage 读取用户上次选中的城市。

## 从城市选择器选城市

用户从省份→城市选择器选中一个城市后，**自动激活同城过滤**：

```javascript
function selectCity(c) {
  if (c) {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      user.city = c
      localStorage.setItem('user', JSON.stringify(user))
    } catch {}
    myCity.value = c
    sameCity.value = true     // ← 选中城市后自动激活过滤
  } else {
    sameCity.value = false    // ← 选"全部城市"则关闭过滤
  }
  load()  // 重新加载数据
}
```

## 点击「同城」按钮

```javascript
function toggleSameCity() {
  if (!sameCity.value) {
    // 要开启过滤
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    if (user.city) {
      myCity.value = user.city
      sameCity.value = true
      load()
    } else {
      safeToast('请先选择所在城市')
      showCityPicker.value = true  // 弹出城市选择器
    }
  } else {
    // 关闭过滤
    sameCity.value = false
    load()
  }
}
```

## API 调用时传参

```javascript
const params = {}
if (sameCity.value && myCity.value) params.city = myCity.value
const res = await api.get('/some/list', { params })
```

## 后端 API 支持

后端需要：
1. 查询参数支持 `city` 字段
2. SQL 用 `u.city LIKE %s` + `f"%{city}%"` 做模糊匹配
3. SELECT 中返回 `u.city` 字段
4. **COUNT 子查询必须保持相同的 JOIN**（参见 `COUNT 子查询 JOIN 陷阱`）

## 应用范围

| 页面 | 状态 |
|------|------|
| 搭子列表（List.vue） | ✅ 已同步 |
| 需求大厅（DemandHall.vue） | ✅ 已同步 |
| 首页（Home.vue） | ❌ 不适用（推荐达人无城市过滤） |
