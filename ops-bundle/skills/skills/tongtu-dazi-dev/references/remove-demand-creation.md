# 取消用户发布需求功能

## 操作清单
取消用户自己发布需求的完整步骤：

### 1. 路由删除
从 `frontend/src/router/index.js` 移除：
```
{ path: '/create-demand', name: 'CreateDemand', component: ... }
{ path: '/register', name: 'Register', component: ... }
{ path: '/follow-register', name: 'FollowRegister', component: ... }
{ path: '/email-register', name: 'EmailRegister', component: ... }
```

### 2. 组件文件删除
```bash
rm -f /opt/ttdazi/frontend/src/views/CreateDemand.vue
rm -f /opt/ttdazi/frontend/src/views/Register.vue
rm -f /opt/ttdazi/frontend/src/views/FollowRegister.vue
rm -f /opt/ttdazi/frontend/src/views/EmailRegister.vue
```

### 3. 前端入口移除
- DemandHall.vue：移除 FAB 创建按钮（`.fab-create`）
- MyDemands.vue：移除「发布需求」按钮和 `goCreate()` 函数
- 空状态提示中的「➕ 发布需求」按钮也要删

### 4. 后端 API 禁用
```python
# demand.py create() 函数
def create():
    return fail('发布功能已关闭')
```

### 5. Profile.vue 修复
`goPlaymate()` 函数中 `router.push('/apply')` 路由不存在，改为 `/companion/register`
