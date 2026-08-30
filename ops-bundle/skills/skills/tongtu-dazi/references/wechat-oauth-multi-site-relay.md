# 微信 OAuth 多站点中转（授权域名复用）

## 背景 / 问题

微信公众号「网页授权域名」和「服务器配置 URL」都只能绑定 **1 个域名**（本项目为 `dazi.openai2000.cn`）。
新站点（如国际站 `www.ttdazi.xyz`）直接在自身域名下发 OAuth 会被微信拒绝，授权回调也只会回到主站。
→ 用户感知：国际站点微信登录 → 授权完被带回主站 ❌

## 解决方案：site 参数编码进 state，回调按白名单跳回

授权始终发生在主站域名下（合法），但回调按 state 中携带的目标站域名跳转。

### 后端（`app/wechat_login.py`）

三个 OAuth 入口全部支持 `site` 查询参数：

```python
@wx_bp.route('/login')
def wx_login():
    site = request.args.get('site', '').strip()
    state = f'ttdazi|{site}' if site else 'ttdazi'
    # redirect_uri 仍是 REDIRECT_URI（主站），但 state 带上目标站
    # state 格式: ttdazi|www.ttdazi.xyz / scan_xxx|www.ttdazi.xyz / reg_xxx|www.ttdazi.xyz
```

`/login-scan`（扫码确认页）与 `/qr-register`（扫码注册）同样处理。

### callback 解析（`wx_callback`）

```python
is_register = state.startswith('reg_')
is_scan_login = state.startswith('scan_')
# 解析站点参数
site = ''
if '|' in state:
    state, site = state.rsplit('|', 1)   # 注意: 先拆掉 site 再判断 scan_code
site = site.strip() if site else ''
allowed_sites = {'www.ttdazi.xyz'}       # ⚠️ 白名单防开放重定向
if site and site not in allowed_sites:
    site = ''
BASE_URL = f'https://{site}' if site else 'https://dazi.openai2000.cn'
scan_code = state[4:] if is_register else (state[5:] if is_scan_login else '')
```

**所有跳转目标**（bind-phone / scan-confirm / wx-login / 注册成功页「进入首页」链接）一律用 `BASE_URL` 拼接，不再硬编码主站域名。

### 前端（Login.vue / Register.vue / ScanConfirm.vue）

按当前域名自动附加 site 参数（同一份 dist 部署两个站，靠 hostname 区分）：

```javascript
function wxSiteParam() {
  const h = window.location.hostname || ''
  if (h === 'www.ttdazi.xyz' || h === 'ttdazi.xyz') {
    return '&site=www.ttdazi.xyz'
  }
  return ''
}
// 调用处:
window.location.href = '/api/wechat/login' + wxSiteParam()
window.location.href = '/api/wechat/login-scan?code=' + code.value + wxSiteParam()
```

### 验证方法

```bash
# 主站行为不变: state=ttdazi
curl -s -m 10 'http://127.0.0.1:5002/api/wechat/login' -o /dev/null -w '%{redirect_url}\n'
# 国际站: state=ttdazi|www.ttdazi.xyz
curl -s -m 10 'http://127.0.0.1:5002/api/wechat/login?site=www.ttdazi.xyz' -o /dev/null -w '%{redirect_url}\n'
# 期望 redirect_url 里出现 state=ttdazi%7Cwww.ttdazi.xyz
```

## 关键陷阱

1. **先拆 site 再解析 scan_code**：`state.rsplit('|', 1)` 必须发生在取 `scan_code` 之前，否则 `scan_xxx|site` 会污染 code。
2. **白名单必须加**：无白名单 = 开放重定向漏洞（攻击者可构造 state 跳任意域名）。
3. **主站零影响**：`site` 为空时 state 格式与原来完全一致，主站逻辑不用动。
4. **同一份 dist 双站部署**：前端靠 `window.location.hostname` 区分，不要为国际站单独维护前端分支。
