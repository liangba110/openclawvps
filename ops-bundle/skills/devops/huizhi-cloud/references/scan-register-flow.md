# 扫码注册流程（两步：手机授权 → PC绑定）

## 流程图

```
PC端                          手机端
┌─────────────────┐           ┌─────────────────┐
│ 扫码Tab → 二维码  │           │                 │
│ 轮询等待扫码     │           │                 │
│                 │ ←──扫码── │ 打开授权页       │
│                 │           │ 显示头像+昵称    │
│                 │           │ 用户点"确认授权"  │
│ 检测status=1     │  ←授权─  │ 授权成功         │
│ 显示绑定表单     │           │ 显示"请在电脑端   │
│ 用户填手机+密码  │           │ 继续完成注册"    │
│ 点"完成注册"    │           │                 │
│ 调用bind API    │           │                 │
│ 自动登录Dashboard│           │                 │
└─────────────────┘           └─────────────────┘
```

## 数据库

`scan_login` 表新增 `extra` 列（VARCHAR(500)），存储手机授权的昵称JSON：`{"nickname": "微信用户"}`

## 状态码

| status | 含义 |
|:------:|:------|
| 0 | 待扫码 |
| 1 | 已扫码/已授权（PC端应显示绑定表单） |
| 2 | 已注册/已完成 |
| -1 | 已过期 |

## 关键API

### 手机授权 `POST /api/register/scan/authorize`
```json
// Request
{"code": "xxx", "nickname": "用户昵称"}
// Response
{"code": 0, "data": {"nickname": "用户昵称"}, "msg": "授权成功"}
```

### PC绑定 `POST /api/register/scan/bind`
```json
// Request
{"code": "xxx", "phone": "13800138000", "password": "xxx"}
// Response
{"code": 0, "data": {"token": "jwt..."}, "msg": "注册成功"}
```

## 注意事项

- PC端轮询检测到status=1时必须停止轮询（clearInterval），避免继续请求
- 切换到"手机注册"Tab时也必须清除轮询定时器，防止后台请求导致页面抖动
- bind接口会检查手机号是否已注册，需调用方提前校验格式
- 前端用 `alert()` 而非 `showToast()` 做错误提示更可靠（避免toast不显示导致用户以为没反应）
