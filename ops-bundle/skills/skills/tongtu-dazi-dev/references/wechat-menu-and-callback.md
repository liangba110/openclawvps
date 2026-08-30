# 微信自定义菜单 + 服务器配置回调（wx_message.py）

模块 `/opt/ttdazi/backend/app/wx_message.py`（Blueprint `/api/wechat`，路由 `/message`），
注册在 main.py。用途：用户点公众号菜单 → 服务器生成验证码 → 客服消息推送；公告/实名认证引导。

## 服务器配置回调（公众号后台"设置与开发 → 基本配置 → 服务器配置"）

| 配置项 | 值 |
|:-----|:-----|
| URL | `https://dazi.openai2000.cn/api/wechat/message` |
| Token | `huizhiyun_ttdazi_2026` |
| 加解密方式 | 明文模式 |

- **GET**：微信后台"提交"按钮发来 `signature/timestamp/nonce/echostr`，
  校验 `sha1(''.join(sorted([Token, timestamp, nonce]))) == signature`，匹配则返回 `echostr`。
- **POST**：接收 XML 消息/事件（用极简正则解析 `<!\[CDATA\[...\]\]>`，无需 xmltodict）。
  - `CLICK` 事件：EventKey → `GET_VERIFY_CODE`（生成6位码存 verify_codes[openid] + 客服消息推送）、
    `NOTICE`（业务公告）、`VERIFY_GUIDE`（实名认证指引）。事件消息被动回复 `success`。
  - `subscribe` 事件：客服消息发欢迎语（含"获取验证码"引导）。
  - 文本消息：含"验证码"关键词 → 触发发码；否则被动回复 XML 引导语。

## 菜单发布：先试 create 直接生效，别急着 publish（关键教训 2026-07-31）

**该公众号（wxd274e174ddadd4cb）是旧版菜单机制：`menu/create` 直接线上生效，不需要 publish！**

排查顺序（省时版）：
1. 先 `menu/create` 完整菜单 → 立即 `get_current_selfmenu_info` 看 `is_menu_open:1` + 内容
2. **若已是 is_menu_open:1 且内容正确 → 菜单已生效，收工**。不要因为想看"发布成功"去调 publish
3. `menu/publish` 对这个账号**永远报 40066 invalid url（即使纯 click 单按钮）**——这是账号机制差异，不是故障，不是菜单内容问题，也**不需要用户去后台开任何功能**
4. 用户微信端菜单最长 60 秒自动刷新，改完等一会儿再点

> ⚠️ 早期误判记录（勿再犯）：曾认为"2020年后必须草稿+发布制、publish 40066=自定义菜单功能被停用需用户后台开启"，
> 为此让用户去开发者平台操作、反复排查账号侧，全部徒劳。真相：**create 即生效**。若 create 后 is_menu_open=0，
> 才考虑账号侧/年审问题。个性化菜单接口 `menu/addconditional` 成功也说明菜单权限正常。

## 40066 invalid url 的真实根因（已确证 2026-07-31）

**这个账号下 40066 的唯一根因：调了 `menu/publish`，而该账号不需要 publish（旧版机制）。**
- view 按钮 URL 含 `#` 报 40066 的猜测：曾把实名认证子按钮 URL `#/verify-identity` 当嫌疑，改成 click 后 publish 仍 40066 → 排除 URL 因素
- "公众号后台自定义菜单功能被停用、需用户去开发者平台开启"的猜测：用户按提示操作后 publish 仍 40066 → 排除账号侧因素
- 最终：**纯 click 单按钮 publish 也 40066 + create 后 is_menu_open 立即=1** → 判定 publish 接口与该账号机制不兼容，create 即生效

诊断技巧：create 完整菜单后直接查 `get_current_selfmenu_info`，is_menu_open:1 即生效；只有 is_menu_open=0 才需要进一步查账号侧。

## 当前状态（2026-07-31 终态）
- **菜单已通过 `menu/create` 直接生效**（最终版：同途搭子/获取验证码/业务公告，无"更多服务"子菜单，实名认证按钮已按用户要求移除）
- wx_message.py 已部署：GET 签名验证/POST CLICK 事件/客服消息推送全部实测通过
- 点菜单本身=与公众号交互 → 刷新 48h 客服消息窗口 → 验证码必达（绕开 45015 窗口限制）
- **阻塞点：公众号后台"服务器配置"尚未启用**（用户端点菜单无事件推送、后端无回调日志）。需用户在公众号后台提交 URL/Token 并点"启用"，启用后 CLICK 事件才会推送进来。诊断方法：`cat /tmp/wx_scan.log` 无"回调:"记录 = 服务器配置未启用
