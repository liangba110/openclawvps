# 同途搭子全量审计清单

## 并行审计方法论

当需要系统性检查前后端时，派发3个并行子代理：

| 审计项 | 范围 | 检查重点 | 输出格式 |
|--------|------|---------|---------|
| 📱 用户端页面 | 25+ .vue | 模板变量、空catch吞错误、safeToast/safeConfirm使用、全局样式统一 | 🔴🟡🟢 |
| 🔧 管理端页面 | 19+ .vue | API路径匹配后端、margin-left:220px、safeConfirm导入、分页功能 | 🔴🟡🟢 |
| 🖥️ 后端API | 27+ .py | 返回值格式({code,data,msg})、字段命名一致性、认证装饰器、参数验证、conn.close() | 🔴🟡🟢 |

## 后端安全审计

### 认证路由检查
```bash
cd /opt/ttdazi/backend
grep -rn "@\w*_bp\.route" app/ | grep -v "__pycache__" | while read line; do
  route=$(echo "$line" | grep -oP "'/\K[^']+")
  file=$(echo "$line" | cut -d: -f1)
  lineno=$(echo "$line" | cut -d: -f2)
  nextline=$(sed -n "$((lineno+1))p" "$file")
  if ! echo "$nextline" | grep -qE "@(login_required|admin_required)"; then
    safe_routes="^list$|^recommend$|^nearby$|^detail$|^health$|^get$|^login$|^register$|^send-code$|^verify-code$|^send-email-code$|^verify-email-code$|^register-by-email$|^register-by-code$|^faq$|^geoip$|^config/list$|^check-agreed$|^agree$|^verify$"
    if ! echo "$route" | grep -qE "$safe_routes"; then
      echo "⚠️ 缺少认证: $file:$lineno → /$route"
    fi
  fi
done
```

### 必须 @admin_required 的管理路由
- 提现管理（withdrawals）
- 优惠券管理（coupon/admin/*）
- 协议管理（agreement/admin/*）
- 审核操作（verify/*, verify/*/approve, verify/*/reject, playmate/*/audit）
- 内容管理（banners, games）
- 代码编辑器（admin/code/*）
- 提现审核（withdrawals/<id>/audit）

### 🔴 常见漏洞（2026-07-06 审计发现）

| 问题 | 文件 | 影响 | 修复 |
|------|------|------|------|
| 提现/优惠券/协议管理路由仅 @login_required | admin.py, coupon.py, agreement.py | 任意用户可审核/修改 | 加 @admin_required |
| register_by_code 使用未定义变量 email | user.py:568 | 手机验证码注册 NameError 崩溃 | 改为 phone |
| playmate_api 重复+错误更新 order_count | playmate_api.py:338 | 统计数异常 | 删除重复更新 |
| 6个页面的admin-main缺 margin-left:220px | 多个admin页面 | sidebar遮挡左上角内容 | 加 margin-left:220px |
| AdminWithdrawals 未导入 safeConfirm | admin/AdminWithdrawals.vue | 提现审核报 ReferenceError | 补导入 |
| AdminUsers 引用不存在的字段 review_count | admin/AdminUsers.vue | 显示 undefined | 改为 order_count |
| AdminReviews 用公共API /review/list | admin/AdminReviews.vue | 权限绕过风险 | 改为 /admin/reviews |
| 13个文件空 catch {} 吞错误 | 多个.vue | 功能失败无提示 | 加 safeToast |
| Reviews.vue rating=0显示5星 | Reviews.vue | 低评分错误展示 | \|\|5 → ??5 |
| platform_review.py 5个审核/举报路由无认证 | platform_review.py | 任意用户可操作审核 | 加 @admin_required |
| attendance.py 3个签到路由无认证 | attendance.py | 无需登录可签到 | 加 @login_required |
| 6个文件 except: pass 吞错误 | companion/faq/cs等 | 错误不可见 | 改为 except Exception: |
| SMTP 密码硬编码在源码 | user.py:639 | 安全风险 | 改为环境变量 |
| 审核操作无 audit_log() | 多处 | 无审计轨迹 | 加 audit_log |

### 常见漏洞
- `except: pass` → 必须 `except Exception:`
- f-string SQL → 确保变量来自白名单字段
- `PWD_MIN_LEN` 默认16→必须改为6（否则注册/改密500崩溃）
- 前端 `catch {}` → 用户操作要有 safeToast，初始加载可静默
- `admin_required` 从 `app.admin` 导入（不在 `app.utils`）

## 邮箱注册陷阱

1. 邮箱拼接必须是 `emailName + '@' + emailDomain`（缺@会导致后端报错）
2. 域名列表存 `qq.com` 不是 `@qq.com`（否则显示 `@@qq.com`）
3. 获取验证码按钮始终可点击（禁用让人迷惑，函数内验证弹Toast）
4. QQ邮箱SMTP会550拒绝不存在的收件人——不是bug
5. 注册按钮禁用条件不要含 `!emailName || !code`，在 doRegister() 内验证
6. refreshCaptcha() 的 catch 必须静默（页面加载自动调用，用户可点图片重试）

## 智能推荐算法

```sql
smart_score = score * 30 + order_count * 0.5 + good_rate * 0.2
ORDER BY is_online DESC, smart_score DESC, LIMIT 8
```

- recommend API：加权评分排序
- nearby API：按游戏分组，每类取前2，混合6条
- list API：新增 recommend/newest 排序选项

## 需求接单权限检查

后端 `POST /api/demand/accept` 内按顺序检查：
1. `user.verify_status = 1`（实名认证通过）
2. `companion.status = 1`（陪玩师审核通过）
任一不通过返回中文提示，不执行接单。

## 前端审计 checklist

### 全局样式统一检查
- 页面使用 `.page` / `.header-bar` / `.card-3d` 全局类
- banner（header-bar/gradient-header）统一 padding: `44px 16px 16px`
- Tab栏统一：`flex-wrap: wrap` 自动换行 + 白底 + 紫色选中态
- 返回箭头 `<span class="back">‹</span>`，22px（header-bar）或 28px（独立定位）
- 需要 `import { smartBack } from '@/utils/nav'` + `useRoute` + `const route = useRoute()`
- 日期用 `formatTime()` 函数，不用 `.slice(0,10)`

### 新建页面 checklist
1. header-bar 导入 smartBack + useRoute + route
2. 覆盖 4 种状态：loading / error / empty / list
3. 3D卡片用 `.card-3d` 类
4. 管理端用 `admin-layout` + `AdminSidebar`
5. 悬浮按钮用 `bottom: 100px` 避开底部导航
6. Tab/分类用 `flex-wrap: wrap` 自动换行
7. 订单号字段 `order_no` 通过 ALTER TABLE 添加后需补全旧数据
