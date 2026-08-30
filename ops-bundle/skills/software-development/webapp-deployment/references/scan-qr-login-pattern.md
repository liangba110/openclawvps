# 微信扫码登录（方案B：自建扫码登录）模式

## 概述

不需要开通微信开放平台（开放平台需 ¥300/年认证费），通过**自建扫码登录**实现 PC 端微信扫码登录。用户手机扫码 → 打开确认页 → 点确认 → PC 自动登录。

## 流程

PC端 POST /api/login/scan/create → 返回 code+code_url → 前端渲染二维码 → 手机扫码打开确认页 → 手机点确认 → PC轮询获取token → 自动跳转

## 后端实现

### 数据库表
```sql
CREATE TABLE scan_login (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(32) NOT NULL UNIQUE,
  status TINYINT DEFAULT 0 COMMENT '0=pending,1=scanned,2=confirmed',
  user_id INT DEFAULT NULL,
  token VARCHAR(500) DEFAULT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  expires_at DATETIME NOT NULL,
  INDEX idx_code (code), INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### API 端点（Flask Blueprint，url_prefix='/api/login'）
- `POST /scan/create` → 生成唯一code，返回{code, code_url, expires_in}
- `GET /scan/status?code=XXX` → 查询状态 0/1/2，已确认时返回token
- `POST /scan/confirm` (@login_required) → FOR UPDATE行锁，生成PC端token

### 关键参数
- CODE_TTL=300秒（5分钟）
- QR_URL=https://域名/#/scan-confirm

## 前端实现
- Login.vue：扫码Tab，自动调用createQr()，1.5s轮询
- ScanConfirm.vue：手机确认页，检查localStorage token，确认后自动返回首页
- 路由：{ path: '/scan-confirm', component: ScanConfirm }

## 移植注意事项
从已有项目复制时需修改：QR_URL、gen_token引用、API路径、前端API endpoint路径、router注册、qrcode npm包安装、scan_login表创建
