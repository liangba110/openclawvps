# softapi 多软件平台 · 接口细节与签名示例

## 签名算法（服务端 verify_sign 实现）
```python
def verify_sign(app_key: str, params: dict, sign: str, timestamp: str) -> bool:
    if abs(int(timestamp) - int(time.time())) > 300:
        return False
    keys = sorted([k for k in params if k not in ('sign', 'timestamp')])
    raw = params.get('app_id', '') + ''.join(f"{k}{params[k]}" for k in keys) + app_key + timestamp
    return md5(raw) == sign
```
关键：排序参数**包含 app_id 本身**（`params.get('app_id','')` 开头 + 排序后的 app_id 键值对会重复出现——这是当前实现，按此计算即可）。

## Python 签名调用示例（实测可用）
```python
import hashlib, time, json, urllib.request

def md5(s): return hashlib.md5(s.encode()).hexdigest()

def signed_call(path, params, app_id, app_key):
    ts = str(int(time.time()))
    p = dict(params); p['app_id'] = app_id
    keys = sorted(p.keys())
    raw = p.get('app_id','') + ''.join(f'{k}{p[k]}' for k in keys) + app_key + ts
    p['sign'] = md5(raw); p['timestamp'] = ts
    req = urllib.request.Request('https://softapi.openai2000.cn'+path,
        data=json.dumps(p).encode(), headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=15).read().decode())

# 用法
APP_ID='APPxxx'; APP_KEY='xxx'
r = signed_call('/api/app/user/login', {'username':'u','password':'p'}, APP_ID, APP_KEY)
token = r['data']['token']
r2 = signed_call('/api/app/recharge/create', {'token':token,'goods_type':2}, APP_ID, APP_KEY)
```

## 关键接口字段
- register: body {app_name, notify_url?, logo_url?} → {app_id, app_key}
- user/register: {app_id, username, password, sign, timestamp} → {user_id}
- user/login: 同上 → {token, user_id, username, vip_type, vip_expire_time}
- user/auth: GET ?app_id=&token= → {user_id, username, vip_type, vip_expire_time}（过期自动降级 vip_type=0）
- recharge/create: {app_id, token, goods_type, sign, timestamp} → {order_sn(SA2...), amount, pay_url(weixin://)}
- recharge/callback: POST 网关格式 {order_no, amount, status} + 头 X-Pay-Token: huizhiyun_gateway_2026 → 自动开权 + 转发软件 notify_url
- page/* 免签名接口：page/login, page/register, page/recharge/create（收银台专用）

## 软件 notify_url 回调格式（本平台转发）
```json
{"app_id":"APPxxx","order_sn":"SA2...","amount":29.9,"goods_type":2,
 "user_id":1,"status":1,"timestamp":"...","sign":"md5(...)"}
```
sign 算法同平台签名（app_id + 排序参数 + app_key + timestamp）。

## 收银台测试流程（浏览器实测）
1. 先建软件：POST /api/app/register 拿 app_id
2. 打开 https://softapi.openai2000.cn/pay/{app_id}/ 应显示软件名
3. 页面注册登录 → 选套餐 → 下单 → 显示二维码
4. 模拟支付：POST /api/app/recharge/callback 带 X-Pay-Token
5. 前端轮询 /api/app/recharge/query 检测 status=1

## 验证 SQL
```sql
-- 开权后核对
SELECT app_id,order_sn,status,notify_status FROM software_auth.app_order ORDER BY id DESC LIMIT 3;
SELECT app_id,username,vip_type,vip_expire_time FROM software_auth.app_user WHERE username='xxx';
```
