# 同途搭子登录安全实现记录

## Token 版本迁移

旧令牌：JWT (create_token in utils.py)，无过期自动刷新
新令牌：v2 自定义格式 (token_auth.py)，30min + refresh_token 7天

兼容做法：`login_required` 装饰器先试 v2，失败降级到 JWT，保证用户不用重新登录。

## 登录流程

```python
# 登录成功
device_id = get_device_id()  # 设备指纹
token = gen_token(user['id'], device_id)  # 30min
refresh_tok = gen_refresh_token(user['id'], device_id, ip)  # 7天
sus, warn_msg = check_anomaly(user['id'], device_id, ip)
return success({
    'token': token,
    'refresh_token': refresh_tok,
    'device_id': device_id,
    'anomaly_warn': warn_msg if sus else '',
    ...user fields...
})
```

## 前端存储

```
localStorage: token, refresh_token, user
```

## 异地检测

后端用 ipinfo.io 查城市，对比 last_city 是否一致。
首次登录：无上一次城市 → 不警告
新设备但同城市 → 轻警告
新城市 → 强警告显示旧城市和当前城市

## 登出

前端调 /user/logout (POST, @login_required)
后端：DELETE FROM refresh_token WHERE user_id=%s
前端：localStorage.clear()

## 刷新

前端 401 → axios 用 refresh_token 调 /user/refresh
返回新 token → local重设 token → 重试原请求
如果 refresh_token 也失效 → 跳登录页

## 关键表

- `refresh_token`: user_id, token, device_id, ip, expires_at — 最多5 rows/user
- `login_log`: user_id, ip, device_id, user_agent, city, is_new_device, is_new_city — 每次登录一行
