# 同途搭子 扫码登录 / 微信OAuth 调试手册

## 症状
用户扫码登录永远提示"登录失败"（`alert("登录失败")`），与用户、网络、手机无关，100% 必现。

## 根因（2026-07-31 定位，经典 Python 陷阱）
`/opt/ttdazi/backend/app/wechat_login.py` 的 `wx_callback()` 函数内部（扫码注册分支）写了：

```python
if is_register and scan_code:
    import json   # ← 函数内 import，坑
```

Python 规则：**函数体内任何位置的 `import json` 都会让 `json` 成为该函数的局部变量**。
导致函数开头 `json.loads(resp.read().decode())` 执行时抛 `UnboundLocalError` → 走 `except` → 返回 `alert("登录失败")`。

修复：删除函数内多余 `import json`（文件顶部第 4 行已有全局导入 `import json, urllib.request, hashlib, time`）。

检查同类问题：搜函数内 `import` / `from ... import`，凡遮蔽了函数前部已使用名字的都必须改为
- 用别名（`import json as j`、`import urllib.request as req`），或
- 移到文件顶部全局导入。

## 为什么之前查不到日志（第二个坑）
`/etc/systemd/system/ttdazi.service` 中 gunicorn 启动参数为 `--log-level warning`，
**gunicorn 会吞掉 worker 的 print 输出**，`journalctl -u ttdazi` 里只有 systemd 启停记录，看不到任何 `[SCAN-LOGIN]` print 日志。

修复：
```bash
sudo sed -i 's/--log-level warning/--log-level info/' /etc/systemd/system/ttdazi.service
sudo systemctl daemon-reload && sudo systemctl restart ttdazi
```

## 日志落盘方案（双保险）
新建共享模块 `/opt/ttdazi/backend/app/scan_log.py`：

```python
"""扫码登录共享日志工具 - 写入 /tmp/wx_scan.log + stdout"""
import time, os

def flog(msg):
    try:
        with open('/tmp/wx_scan.log', 'a', encoding='utf-8') as f:
            f.write(f'[{time.strftime("%m-%d %H:%M:%S")}] {msg}\n')
    except Exception:
        pass
    print(f'[SCAN-LOGIN] {msg}', flush=True)
```

在 `wechat_login.py` / `scan_login.py` 中：
```python
from app.scan_log import flog as _flog
```
关键节点全部埋点：callback 进入、token 换取成功/异常（含 errcode 详情）、scan 分支、phone_bound、redirect 目标、scan/status status=2、bind-phone token 有效性。

## 无手机时的验证方法
用无效 code 直接 curl 回调，可验证日志链路和错误分支：
```bash
curl -s 'http://127.0.0.1:5002/api/wechat/callback?code=test_invalid_code_123&state=scan_testcode1234'
cat /tmp/wx_scan.log
```
- 返回 `alert("微信错误")` + 日志 `微信返回错误 {'errcode': 40029...}` = 正常（code 无效预期行为）
- 返回 `alert("登录失败")` = token 换取异常（如上 UnboundLocalError）

## 前端确认链路（此前已修好的点，勿回退）
- `ScanConfirm.vue`：auto confirm 必须等 `/user/profile` fetch 完成后（`hasToken` 更新）再执行
- `BindPhone.vue` 绑完跳回 `scan-confirm` 必须带 `auto=1`
- PC 端 `ScanLogin.vue` / `Login.vue` 轮询 `/login/scan/status`，status=2 且带 token 才算成功
