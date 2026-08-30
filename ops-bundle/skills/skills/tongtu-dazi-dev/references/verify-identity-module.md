# 实名认证模块（VerifyIdentity.vue）

## 页面流程

```
Step 1: 隐私协议弹窗 (`step === 1`)
  └─ 勾选同意 → 按钮变为「我同意，开始认证」
Step 2: 上传身份证 + 填写信息 (`step === 2`)
  ├─ 上传身份证正面（人像面）
  ├─ 上传身份证背面（国徽面）  
  ├─ 真实姓名（仅汉字）
  └─ 身份证号 → 提交审核
Step 3: 提交成功 / 审核中 (`step === 3`)
  └─ 显示「提交成功，请等待审核」，可返回个人中心
```

## 状态保护

| 用户状态 | 设置页行为 | 验证页行为 |
|---------|-----------|-----------|
| verify_status=0（未认证） | 跳转验证页 | 显示 Step1 弹窗 |
| verify_status=1（已认证） | Toast「已实名认证，不可修改」 | userVerified=true，无操作权限 |
| verify_status=2（审核中） | Toast「审核中，请耐心等待」 | userVerified=true，跳 Step3 显示审核中 |

代码中的检查点：
```
// 从 localStorage 读取初始状态
if (user && (user.verify_status == 1 || user.verify_status == 2 || user.verified)) {
  userVerified.value = true
}

// uploadId 函数保护
function uploadId(side) {
  if (userVerified.value) { safeToast('审核中，请等待'); return }
  ...
}

// submitVerify 函数保护
async function submitVerify() {
  if (userVerified.value) { safeToast('已提交审核，请等待'); return }
  ...
}
```

## CSS 类名坑点

模板中使用 `pd-*` 类名（pd-icon, pd-body, pd-agree, pd-check, pd-btn, pd-tip），
但 scoped CSS 必须匹配这些类名。不能出现模板用 `pd-*` 而 CSS 用 `privacy-*` 的情况 ——
会导致弹窗完全无样式。

检查方法：
```bash
# 确认模板类名在 CSS 中有对应定义
grep "class=\"" file.vue | grep -o 'pd-[a-z]*' | sort -u
grep "^\." file.vue | grep -o 'pd-[a-z]*' | sort -u
# 对比两组输出是否一致
```

## 图片上传

### 前端限制
```js
if (file.size > 5 * 1024 * 1024) {
  safeToast('图片大小不能超过5MB')
  e.target.value = ''
  return
}
```

### 文件上传后清空 input 允许重复选择
```js
} finally {
  e.target.value = ''
}
```

### 后端保存路径

Flask 静态文件服务路径：
```python
# main.py 中
upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'uploads')
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(upload_dir, filename)
```

上传 ID 卡片时必须保存到 `/opt/ttdazi/backend/app/uploads/idcards/`：

```python
upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'uploads', 'idcards')
```

**不要**保存到 `/opt/ttdazi/backend/uploads/idcards/`（少一层 `app`），虽然文件存在但 Flask 路由找不到。

## 姓名输入限制

```html
@input="realName = realName.replace(/[^\u4e00-\u9fa5]/g,'').slice(0,10)"
```

- 只保留 Unicode 汉字范围（U+4E00–U+9FA5）
- 最多 10 个字
- 在 Vue 模板中 `\u4e00` 会被正确解析为汉字起始字符

## 提交后跳转

提交成功后 `window.location.hash = '#/settings'`（不使用 `router.push` 以避免 router 实例引用问题）。
