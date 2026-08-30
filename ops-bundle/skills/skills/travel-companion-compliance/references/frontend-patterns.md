# 旅游搭子前端实现模式

## 首页双卡片入口

位于"热门搭子"上方，左右并排两个渐变卡片：

```html
<div class="dual-cards">
  <div class="entry-card entry-game" @click="$router.push('/list?type=game')">
    <div class="ec-icon">🎮</div>
    <div class="ec-title">游戏搭子</div>
    <div class="ec-desc">组队·上分·技术交流</div>
  </div>
  <div class="entry-card entry-travel" @click="goTravelList">
    <div class="ec-icon">🏛️</div>
    <div class="ec-title">旅游搭子</div>
    <div class="ec-desc">向导·旅拍·美食·徒步</div>
  </div>
</div>
```

```css
.dual-cards { display:flex; gap:12px; margin:0 16px 16px; }
.entry-card { flex:1; border-radius:16px; padding:20px 14px; cursor:pointer;
  display:flex; flex-direction:column; align-items:center; gap:6px;
  min-height:100px; justify-content:center; text-align:center; }
.entry-game { background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; }
.entry-travel { background:linear-gradient(135deg,#11998e,#38ef7d); color:#fff; }
```

## 列表页分类筛选

List.vue 支持 `?type=travel` 和 `?type=game` 参数：

```javascript
const isTravel = computed(() => route.query.type === 'travel')

// 加载分类
if (isTravel.value) {
  games.value = (allGames || []).filter(g => g.id >= 8)
} else {
  games.value = (allGames || []).filter(g => g.id < 8)
}

// API 请求
params.type = isTravel.value ? 'travel' : 'game'
```

## 聊天合规弹窗

CustomerService.vue 进入页自动弹出：

```javascript
const showCompliance = ref(true)
const complianceElapsed = ref(false)
setTimeout(() => { complianceElapsed.value = true }, 3000)
```
