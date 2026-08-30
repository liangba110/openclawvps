# 2026-07-07 全量审计发现汇总

## 后端安全（9个高危）

已修复：
- admin.py 提现路由无 `@admin_required`（仅`@login_required`）
- coupon.py 管理路由无 `@admin_required`
- agreement.py 管理路由无 `@admin_required`
- platform_review.py 5个审核/举报路由无任何认证 → 加 `@admin_required`
- attendance.py 3个签到路由无认证 → 加 `@login_required`
- 6个文件 bare `except:` 吞错误 → 改为 `except Exception:`

Bug修复：
- user.py `register_by_code()` 使用未定义变量 `email`（应为 `phone`）→ 导致NameError崩溃
- playmate_api.py 完成订单时重复更新 `order_count`（companion user和ordering user都更新）→ 清理错误代码
- utils.py 密码验证要求16位+大小写+特殊字符 → 改为6位+数字

## 前端审计（31个🔴 + 22个🟡）

修复：
- 13个文件空 `catch {}` 加 `safeToast`
- Reviews.vue `item.rating || 5` → `item.rating ?? 5`（rating=0显示5星bug）
- 8个admin页面 `margin-left:220px` 修复sidebar遮挡
- AdminWithdrawals 未导入 `safeConfirm`
- AdminUsers 引用不存在字段 `review_count` → 改为 `order_count`
- AdminReviews 使用公共API `/review/list` → 改为 `/admin/reviews`

## 返回箭头统一

- Profile: 自定义 `profile-back` → 标准 `<span class="back">`
- List: `gradient-header` 内 `listed-header` → 统一absolute定位
- Coupon/Detail/CreateOrder/Download/Verificatoin/VerifyIdentity: 全部补上
- CSS统一：22px白色，`line-height:1`
- 必须导入 `useRoute` + `const route = useRoute()`（经常漏）

## Logo设计流程

1. 创建HTML（内联SVG + grid布局 + 预览卡片）
2. Python http.server 本地提供文件
3. Playwright 截图发给用户
4. 用户确认后替换 `/public/favicon.svg` 和 `/public/logo/*.svg`
5. 打包到下载页面 `ttdazi_logos_v3.zip`

## CSS `\n` 转义修复

`patch` 工具写 `\\n` 时会被序列化为字面量 `\n`（反斜杠+n）。修复：
```python
with open('file', 'rb') as f: data = f.read()
data = data.replace(b'\\n', b'\n')
with open('file', 'wb') as f: f.write(data)
```
