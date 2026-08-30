# 同途搭子 — 返回箭头规范 + 常见Bug模式 + Banner高度

## 返回箭头统一规范

所有用户端页面必须统一（❌不需要返回箭头的页面：Login, Register, EmailRegister, FollowRegister, Home, CompanionRegister）：

| 属性 | 值 |
|------|-----|
| 符号 | `‹` |
| 字号 | **22px**（匹配全局 `.header-bar .back`） |
| 颜色 | `#fff` |
| 点击 | `@click="smartBack(route.path)"` |
| 必须导入 | `import { smartBack } from '@/utils/nav'` |
| 必须导入 | `import { useRoute } from 'vue-router'` + `const route = useRoute()` |

### ⚠️ ❌ 最常见的错误
- **只导入了`useRouter`没导入`useRoute`** → `route`未定义 → `route.path`为undefined → `smartBack()`拿不到路径 → 箭头点击无反应。修复：加 `import { useRoute }` 和 `const route = useRoute()`。**Vue 3 `<script setup>` 中不会报错**（静默传递undefined），功能静默失效。
- **同时使用内联style + scoped CSS** → 两者 font-size/z-index/top/left 值不同 → 实际渲染效果不可预期。**必须只用一个**（Profile.vue 曾因此 fix-size 22px vs 28px 冲突）。

### 各页面的实现方式（完整清单 2026-07-06 审计）

| 页面 | 类型 | 实现方式 | 关键CSS |
|------|------|---------|---------|
| Orders, Settings, Messages, Favorites, Reviews, Coupons, About, Security, CustomerService, MyFeedback, MessageDetail | ✅ 标准 `.header-bar` | `<span class="back">` 直接放在 header-bar 内 | 全局 `.header-bar .back { font-size:22px; color:#fff; }` |
| Agreement (4个协议) | ✅ 标准 `.header-bar` | 同上 | 同上 |
| CreateOrder, VerifyIdentity | ✅ 已修复 | `<span class="back">` 在 header-bar 内 | 同上 |
| Profile | ⚠️ 自定义 `.profile-header` | 内联style | `position:absolute; top:12px; left:14px; z-index:999; font-size:22px; color:#fff;` — **不要**同时设scoped CSS |
| List | ⚠️ 自定义 `.gradient-header` | 内联style absolute | `position:absolute; left:14px; top:44px; font-size:22px;` + header `text-align:center` 居中标题 |
| Detail | ⚠️ hero图覆盖 | `<span class="back detail-back">` | `position:absolute; top:12px; left:12px; z-index:10; font-size:28px;` |
| TeamBoard | ⚠️ 独立页面 | 内联style fixed | `position:fixed; top:12px; left:12px; z-index:100; font-size:22px; color:#667eea;` |
| Verification | ⚠️ 登录卡片内 | `<span class="back">` 在 login-card 顶部 | `display:block; font-size:22px; color:#667eea; text-align:left;` |
| Download | ⚠️ 深色背景独立页 | 半透 header-bar fixed | `background:rgba(0,0,0,0.2); position:fixed; top:0; z-index:10;` |

### 常见CSS冲突
- `position:absolute`没设`z-index` → 被头像/装饰元素遮挡
- `overflow:hidden`在父容器（如`.profile-header`） → 裁剪absolute子元素（已移除）
- 父容器的 `::before` 或 `::after` 伪元素若有背景/定位 → 可能覆盖absolute箭头
- **Profile.vue 特别注意事项**：
  - `.profile-header` 曾设 `overflow: hidden` → 移除（遮挡箭头）
  - `.profile-header .back` scoped CSS 与内联style冲突（font-size 28px vs 22px, z-index 10 vs 20）→ 删除scoped CSS，只用内联style唯一来源
  - `.avatar-wrap` 有 `z-index: 10` → 箭头 `z-index` 必须 > 10（设为 999）
  - 装饰 `::before` 圆(160px) 在右上角（`top:-60px; right:-40px`）→ 不影响左上箭头
  - 箭头 `top` 值需低于头像上边缘（头像 `padding:24px 0 56px`，头像在居中）→ `top:12px` 合适

## 页面 Banner 高度标准

| 页面类型 | 顶部结构 | 标准padding |
|---------|---------|------------|
| 标准页（Settings, Messages等） | `.header-bar` | 全局已定义 |
| Orders/Messages（有Tab栏） | header-bar + tab-bar | tab padding: `14px 8px`（增大时）, `8px 8px`（减小时） |
| Profile | `.profile-header` | `padding: 24px 0 56px`（紧凑）, `40px 0 80px`（宽松） |
| List | `.gradient-header` | `padding: 44px 20px 20px` |

## 密码验证Bug
- 后端 `PWD_MIN_LEN = 16`（含大写+小写+数字+特殊字符）
- 前端验证6位+数字
- 用户用6位密码→前端通过→后端500崩溃
- **修复**：`PWD_MIN_LEN = 6`，只保留数字检查
- 修改后需清`__pycache__`+重启gunicorn

## `conn`变量作用域Bug
- `conn = get_connection()` 在 `if` 块内定义
- 块外引用时 `NameError: name 'conn' is not defined`
- **修复**：在`try`块顶部统一`conn = get_connection()`

## 邮箱注册流程要点
- `emailName + '@' + emailDomain`（域名列表不带@前缀）
- 点击获取验证码直接调`/user/send-email-code`API，不要弹公众号二维码
- 注册按钮始终可点击（仅loading禁用），校验在函数内弹Toast
- 完整API流程：`send-email-code`→`verify-email-code`→`register-by-email`

## 全量审计清单
同时审计三个层面（推荐并行subagent）：
1. **后端API**：认证装饰器、返回值格式、字段命名、参数验证、f-string SQL、数据库连接关闭、bare except
2. **前端页面**：模板变量、数据显示条件、catch吞错误、全局样式使用、空catch
3. **管理端页面**：API路径匹配、admin-layout布局、safeConfirm导入、分页、margin-left:220px

## 修改密码后需重启步骤
修改 `utils.py` 后必须：`find /opt/ttdazi/backend -name "__pycache__" -type d -exec rm -rf {} +` → `systemctl restart ttdazi`
