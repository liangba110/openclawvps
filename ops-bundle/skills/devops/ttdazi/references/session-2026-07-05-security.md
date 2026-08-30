# 同途搭子 2026-07-05 会话产出

## 修复列表

| BUG | 描述 | 提交 |
|-----|------|------|
| BUG-001 | 搜索功能: 列表页搜索框+后端LIKE模糊匹配 | ec178d8 |
| BUG-002 | 陪玩师重复数据: 清理2组+唯一索引 | ad0eca6 |
| BUG-003 | 收藏视觉反馈: 心形缩放动画+Pulse | cfe78e1 |
| BUG-004 | 相册空状态: 显示"暂无生活照" | cfe78e1 |
| BUG-005 | 清理测试数据: 6个测试账号 | cfe78e1 |
| BUG-006 | 默认头像: avatars目录symlink | 3f7a797 |
| BUG-007 | 日期格式: str(datetime)[:19] | 3f7a797 |
| BUG-008 | 个人中心"未知": 无城市不显示 | 3f7a797 |
| BUG-009 | 图标重复: 全部📋+热门🔥 | 3f7a797 |
| 头像404 | 相对路径→window.location.origin | 15a35c0/eb40729 |

## 安全加固清单 (按部署顺序)

1. **main.py**: 关闭 DEBUG, 全局 errorhandler(500/404/405), traceback 仅日志
2. **captcha.py**: 算术验证码, 5分钟过期
3. **ratelimit.py**: IP限流(5/min), 密码锁定(3次/10min), 验证码频率
4. **token_auth.py**: v2 token(30min) + refresh(7天) + 设备绑定 + 异地检测
5. **audit_log.py**: 登录/登出/下单审计, 含IP+UA+详情
6. **safety_filter.py**: XSS(sanitize)+脱敏(mask_phone)+分页(paginate)
7. **payment_secure.py**: DB价格强制+幂等锁(idempotent)
8. **risk_control.py**: 批量注册(3/天/IP)+高频下单(10/天/用户)
9. **security_api.py**: 设备管理列表+改密(邮箱验证码)
10. **platform_review.py**: 敏感词过滤+实名认证+举报
11. **nginx/iptables**: 并发限制+UA过滤+IP封禁

## 关键提交

```bash
ea7fe10  基础防护(堆栈关闭+审计+防火墙)
78f8427  v2 token+refresh+异地检测+服务端登出
967052f  XSS过滤+脱敏+强制分页
d9d0de0  风控(IP封禁+批量注册+高频下单)
f60c969  账号安全(设备管理+改密)
d93e5b9  实名认证(隐私协议+OCR+身份证校验)
1d92458  全局异常拦截
```

## 新增文件清单

```
backend/app/token_auth.py      # token安全模块
backend/app/audit_log.py        # 审计日志
backend/app/safety_filter.py    # 输入输出过滤
backend/app/risk_control.py     # 风控管控
backend/app/security_api.py     # 账号安全API
backend/app/platform_review.py  # 平台审核
backend/app/payment_secure.py   # 资金安全
backend/app/captcha.py          # 图形验证码
frontend/src/views/Security.vue       # 账号安全页
frontend/src/views/VerifyIdentity.vue  # 实名认证页
```
