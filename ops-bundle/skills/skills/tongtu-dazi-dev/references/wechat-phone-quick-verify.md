# 微信手机号快速验证（H5 网页）

## 背景

公众号网页授权（`snsapi_userinfo`）只能获取昵称/头像，**无法直接获取手机号**。

## 方案选型

| 方案 | 适用场景 | 要求 | 用户交互 |
|------|---------|------|---------|
| ✅ `wx.getPhoneNumber` (JSAPI) | 微信内置浏览器 | 认证服务号 + JS-SDK 1.6.0+ | 弹窗点「同意」|
| ❌ 短信验证码 | 所有浏览器 | 短信服务费 | 输入手机号+验证码 |
| ❌ 开放标签 | 微信内置浏览器 | 认证服务号 + 开放标签 | 点按钮弹窗 |

**推荐：** `wx.getPhoneNumber` JSAPI

## 完整流程

```
① 微信内打开 H5 页面
② 公众号 OAuth 授权 → 拿到 openid
③ 调用 wx.getPhoneNumber() → 用户点同意 → 返回 code
④ 后端用 code 换手机号
   POST https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token=ACCESS_TOKEN
   Body: {"code": "..."}
   Response: {"errcode":0, "phone_info":{"phoneNumber":"138..."}}
⑤ 存储 phone 到 user 表
```

## 必要条件

- 公众号必须是 **认证服务号**（未认证不弹授权窗）
- 公众号后台 → 功能 → 手机号验证 → **开启**
- JS接口安全域名已添加

## 后端 API

### wxphone 端点

```python
@wx_bp.route('/wxphone', methods=['POST'])
def wx_get_phone():
    token = data.get('token', '')
    code = data.get('code', '')
    # 验证用户 token
    payload = decode_token(token)
    user_id = payload['user_id']
    # 获取 access_token
    token_url = f'https://api.weixin.qq.com/cgi-bin/token?...'
    access_token = json.loads(urllib.request.urlopen(token_url).read())['access_token']
    # 用 code 换手机号
    resp = urllib.request.urlopen(urllib.request.Request(
        f'https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={access_token}',
        data=json.dumps({'code': code}).encode(),
        headers={'Content-Type': 'application/json'}))
    result = json.loads(resp.read().decode())
    phone = result['phone_info']['phoneNumber']
    # 绑定到用户
    UPDATE user SET phone=%s, phone_bound=1 WHERE id=%s
```

## 前端

```javascript
// 1. 检测微信浏览器
const isWechat = navigator.userAgent.toLowerCase().includes('micromessenger')

// 2. 加载 JS-SDK + 配置
const script = document.createElement('script')
script.src = 'https://res.wx.qq.com/open/js/jweixin-1.6.0.js'
script.onload = () => {
  fetch('/api/wechat/config').then(r=>r.json()).then(res => {
    if (res.code === 0) wx.config({...res.data, jsApiList: ['getPhoneNumber']})
  })
}

// 3. 用户点击 → 调起授权
function wxGetPhone() {
  wx.getPhoneNumber({
    success: (res) => bindPhone(res.code),  // res.code 是临时 code
    fail: (err) => alert('获取手机号失败')
  })
}

// 4. 后端解密
async function bindPhone(code) {
  const r = await fetch('/api/wechat/wxphone', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({token, code})
  }).then(r=>r.json())
}
```

## 降级策略

非微信浏览器中不显示微信获取按钮，改为手动输入手机号直接保存（无验证码）。由前端 `isWechat` 变量控制显示哪个交互模块。
