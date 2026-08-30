# 公众号验证码系统（wx_code.py）— 通过微信客服消息发验证码

独立验证码模块 `/opt/ttdazi/backend/app/wx_code.py`（Blueprint `/api/wxcode`），
类似手机验证码但走微信公众号推送（平台未接真实短信服务，替代 `wx_send_code` 的测试模式 print）。

## 接口
| 接口 | 说明 |
|:-----|:-----|
| `POST /api/wxcode/send` | 需登录。生成6位验证码 → 公众号客服消息推到用户微信。60s限流、5分钟有效 |
| `POST /api/wxcode/verify` | 校验验证码（openid 或 phone 维度），无需登录 |
| `POST /api/wxcode/bind-phone` | 需登录。校验验证码 + 绑定手机号（防重复绑定） |

数据库：`verify_codes` 表新增 `openid VARCHAR(64)` 列（ALTER TABLE 已执行）。

## 微信 API 关键限制（踩坑）
1. **客服消息 48h 交互窗口**：`cgi-bin/message/custom/send` 要求用户**48小时内与公众号有交互**
   （网页授权/扫码登录/在公众号发消息都会刷新窗口）。超窗报错：
   ```
   {"errcode":45015,"errmsg":"response out of time limit or subscription is canceled"}
   ```
   处理：发送失败时回滚验证码（DELETE），提示用户"请在公众号内先发送任意消息激活通道，或重新扫码登录后重试"。
   真实场景 OK：用户扫码登录时网页授权刚发生，窗口有效，绑定手机号能正常收到。

2. **账号能力探测**（开发前先确认）：
   ```bash
   # 公众号类型：account_type=2 服务号（可客服消息/模板消息）；=0 订阅号受限
   curl "https://api.weixin.qq.com/cgi-bin/account/getaccountbasicinfo?access_token=$TOK"
   # 用户关注状态：subscribe=1 已关注
   curl "https://api.weixin.qq.com/cgi-bin/user/info?access_token=$TOK&openid=$OPENID&lang=zh_CN"
   # 粉丝数：cgi-bin/user/get?access_token=$TOK&next_openid=
   # 已有模板：cgi-bin/template/get_all_private_template?access_token=$TOK
   ```
   本账号：已认证服务号（胶州市汇智云互联网络工作室），粉丝 2 人，已有订阅模板
   `nDvnB8ZweeVxWi61Azh7Se_gnmbHFyRJ4LePtdE9pL8`（`{{content.DATA}}`）。
   `template/get_industry` 报 40102 invalid industry id = 行业未设置，模板消息暂不可用，用客服消息即可。

3. **access_token 缓存**：7200s 有效期，代码内用模块级 dict 缓存 7000s 刷新，避免每次请求都换 token。

## 前端
`BindPhone.vue` 已改造：手机号 + "获取验证码"按钮（60s倒计时）→ 验证码发到微信 → 输入后绑定。
提示语："验证码已发送到您的微信，请查看公众号消息"。

## ⚠️ 测试教训：改真实用户数据必须立即恢复
测试 bind-phone 时用了**真实用户** 10047 的 token，把其手机号改成了测试号。
恢复方法（从 Server A 数据盘备份查原值）：
```bash
scp root@42.193.113.230:/root/data/disk/daily_<日期>_*/huizhiyun_database.sql /tmp/bk.sql
# user 表 INSERT 是多行 VALUES，按列序找 phone 列
grep -an 'INSERT INTO `user`' /tmp/bk.sql
mysql -uroot -phuizhiyun2026 huizhiyun -e "UPDATE user SET phone='原值', phone_bound=1 WHERE id=10047;"
```
**教训**：凡是会写用户数据的接口（bind-phone/verify/balance），测试一律用测试专用账号，
或测完立刻从备份恢复。不要用真实用户 ID 生成 token 测写操作。
