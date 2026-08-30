# 内容安全过滤系统（app/ad_filter.py）

## 概述

`app/ad_filter.py` 提供全自动的违规内容检测 + 封禁冻结机制。检测到引流/线下交易内容时，自动执行：余额归零 → 账号永久封禁 → 陪玩师下架。

## 检测规则

| 规则 | 正则/匹配 | 示例抓取 |
|------|-----------|---------|
| QQ号 (纯数字) | `[1-9]\d{4,10}` | 12345678 |
| 微信号 (文字+ID) | `微信号?[：:\s]*[a-zA-Z]\w{5,19}` | 微信号：abc123 |
| 手机号 | `1[3-9]\d{9}` | 13900139000 |
| 敏感词库 | `sensitive_words` 表 | 微信/QQ/扫码/加我/收款 |
| 引流/线下引导 | 硬编码正则 | 私我/私下交易/绕过平台 |

## 处罚流程（分级）

| 次数 | 处罚 | 实现 |
|------|------|------|
| 1 | ⚠️ 警告 | violation_log + user_penalty.count=1 |
| 2 | 🔒 封禁3天 | user.status=0, banned_until=NOW+3天 |
| 3 | 🚫 永久封禁+下架 | user.status=0, companion.status=0 |

## 数据库表

```sql
CREATE TABLE violation_log (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    violation_type VARCHAR(30) DEFAULT 'ad',
    content TEXT,
    penalty VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user (user_id)
);
CREATE TABLE user_penalty (
    user_id INT UNSIGNED PRIMARY KEY,
    violation_count INT DEFAULT 0,
    banned_until DATETIME,
    permanently_banned TINYINT DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## check_and_punish 返回消息

| 次数 | 返回值 |
|------|--------|
| 1 | '⚠️ 检测到违规内容（{原因}），本次警告，二次违规将封禁3天，三次永久封禁' |
| 2 | '⚠️ 您已二次违规（{原因}），账号已封禁3天，请遵守平台规则' |
| 3 | '🚫 您已多次违规（{原因}），账号已被永久封禁，陪玩师已下架，资金已冻结' |

## 已覆盖入口

- companion.py: register() intro, update_profile() intro
- chat.py: send() 消息内容
- demand.py: create() title/description

## ⚠️ 误杀清单

"辅助"、 "代打"、"代练"已从敏感词表删除（游戏术语）。新增敏感词前检查是否误杀正常游戏用语。
