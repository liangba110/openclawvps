# Vue 全局 CSS 设计系统 — 同途搭子实战记录

## 起源

2026-07-06 当网站页面增加到 25+ 时，每个页面都自己写 scoped style：
- `page-container` 容器
- `gradient-header`/`page-header`/`settings-header`/`msg-header`/`ps-header`/`ag-header` 顶栏
- `order-card`/`review-card`/`detail-card`/`ag-card` 卡片
- `action-btn.primary`/`ps-btn` 按钮

重复样式导致：
1. 同一渐变色值在 25 个文件出现 50+ 次，改主题色要逐个文件改
2. 卡片阴影、圆角不统一（有的 8px 有的 16px 有的 20px）
3. 安全漏洞：改一个忘记另一个
4. 维护成本指数级增长

## 完整设计系统（2026-07-06 定稿）

所有全局类都在 `frontend/src/assets/global.css` 中定义，**后续页面禁止再自定义类，必须用全局类**：

```css
/* === 容器 === */
.page {
  min-height: 100vh;
  background: #f5f6fa;
  padding-bottom: 80px;
}

/* === 顶栏（全站统一） === */
.header-bar {
  display: flex;
  align-items: center;
  padding: 14px 16px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  gap: 12px;
}
.header-bar .back {
  font-size: 22px;
  cursor: pointer;
}
.header-bar .title {
  font-size: 17px;
  font-weight: 700;
  flex: 1;
  text-align: center;
}
.header-bar .right {
  width: 28px;
}

/* === 卡片 === */
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin: 12px 16px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}

/* === 菜单项 === */
.menu-item {
  display: flex;
  align-items: center;
  padding: 15px 16px;
  background: #fff;
  border-radius: 12px;
  margin-bottom: 10px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
  cursor: pointer;
  transition: transform 0.15s;
}
.menu-item:active {
  transform: scale(0.98);
}
.menu-item .mi-icon {
  width: 38px; height: 38px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; margin-right: 12px; flex-shrink: 0;
}
.menu-item .mi-info { flex: 1; min-width: 0; }
.menu-item .mi-title { font-size: 14px; color: #333; font-weight: 500; }
.menu-item .mi-desc { font-size: 11px; color: #bbb; margin-top: 2px; }
.menu-item .mi-arrow { font-size: 20px; color: #ddd; margin-left: 8px; flex-shrink: 0; }

/* === 按钮 === */
.btn-primary {
  border: none; border-radius: 10px;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff; font-size: 15px; font-weight: 600;
  padding: 12px 0; cursor: pointer; text-align: center;
  transition: opacity 0.15s;
}
.btn-primary:active { opacity: 0.85; }
.btn-primary:disabled { opacity: 0.5; }

/* === 输入框 === */
.input-field {
  width: 100%; padding: 11px 14px;
  border: 1px solid #eee; border-radius: 10px;
  font-size: 14px; outline: none; box-sizing: border-box;
  background: #fff;
}
.input-field:focus { border-color: #667eea; }

/* === 徽章/标签 === */
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-blue   { background: #e3f2fd; color: #1565c0; }
.badge-green  { background: #e8f5e9; color: #2e7d32; }
.badge-red    { background: #ffebee; color: #c62828; }
.badge-orange { background: #fff3e0; color: #e65100; }
.badge-purple { background: #f3e5f5; color: #7b1fa2; }

/* === 空状态 === */
.empty-state { text-align: center; padding: 60px 20px; }
.empty-state .empty-icon { font-size: 56px; opacity: 0.4; margin-bottom: 10px; }
.empty-state .empty-text { font-size: 14px; color: #888; }

/* === 表单 === */
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; font-weight: 600; color: #555; margin-bottom: 4px; }

/* === 分段标题 === */
.section-label { padding: 4px 16px 8px; font-size: 13px; color: #999; font-weight: 600; }

/* === 弹窗（与 toast/confirm 共享） === */
.custom-loading-overlay { position: fixed; inset: 0; z-index: 2147483646; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.35); }
.custom-loading-box { background: rgba(255,255,255,0.95); border-radius: 12px; padding: 28px 36px; text-align: center; box-shadow: 0 8px 30px rgba(0,0,0,0.15); }
.custom-loading-spinner { width: 32px; height: 32px; border: 3px solid #e0e0e0; border-top-color: #667eea; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 10px; }
.custom-loading-text { font-size: 14px; color: #666; }

.custom-confirm-overlay { position: fixed; inset: 0; z-index: 2147483647; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.45); animation: fadeIn 0.2s ease; }
.custom-confirm-box { background: #fff; border-radius: 14px; width: 300px; max-width: 85%; overflow: hidden; box-shadow: 0 12px 40px rgba(0,0,0,0.2); animation: scaleIn 0.2s ease; }
.custom-confirm-title { text-align: center; font-size: 16px; font-weight: 700; color: #333; padding: 22px 20px 6px; }
.custom-confirm-message { text-align: center; font-size: 14px; color: #666; padding: 8px 20px 20px; line-height: 1.5; }
.custom-confirm-btns { display: flex; border-top: 1px solid #f0f0f0; }
.custom-confirm-btn { flex: 1; border: none; background: #fff; font-size: 15px; padding: 14px 0; cursor: pointer; }
.custom-confirm-btn.cancel-btn { color: #666; border-right: 1px solid #f0f0f0; }
.custom-confirm-btn.confirm-btn { color: #667eea; font-weight: 600; }

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes scaleIn { from { transform: scale(0.9); opacity: 0; } to { transform: scale(1); opacity: 1; } }
```

## Batch Migration Workflow (10+ pages)

### Step 1: 定义全局类（一次）

在 `global.css` 末尾追加所有统一类。一次到位，不要反复改。

### Step 2: 列出所有需要改造的页面

```bash
# 扫描所有 .vue 文件，找出页面级 scoped style
find frontend/src/views -name "*.vue" -exec grep -l '<style scoped>' {} \;
```

### Step 3: 并行子代理处理（关键加速）

```python
# 用 delegate_task 同时派发多个子代理，每个处理 5-10 个页面
# 关键：给出精确的「替换清单」和「陷阱警告」
tasks = [
    { 'goal': '改造 Orders/Settings/Security 等 5 页', 'files': [...] },
    { 'goal': '改造 Favorites/Reviews/Coupons/About/Download 等 5 页', 'files': [...] },
    { 'goal': '改造 Messages/MessageDetail', 'files': [...] },
]
# 每个子代理：read_file → patch template → patch style → 报告
```

### Step 4: 全局验证

```bash
# 应该找不到遗留的自定义类
grep -rn "page-container" frontend/src/views/
grep -rn "gradient-header" frontend/src/views/
grep -rn "page-header" frontend/src/views/  # Settings.vue 等
# 应该找到大量新类
grep -rn 'class="page"' frontend/src/views/ | wc -l
grep -rn 'class="card"' frontend/src/views/ | wc -l
grep -rn 'class="header-bar"' frontend/src/views/ | wc -l
```

### Step 5: 构建部署

```bash
cd frontend && npm run build && bash /opt/ttdazi/deploy.sh
```

## 改造前后对比

### 之前：每个页面 ~100-200 行重复样式

```vue
<!-- Orders.vue -->
<style scoped>
.page-container { min-height: 100vh; background: #f5f5f5; padding-bottom: 80px; }
.gradient-header { background: linear-gradient(135deg, #667eea, #764ba2); ... }
.order-card { background: #fff; border-radius: 12px; padding: 16px; ... }
...100 行重复定义
</style>
```

### 之后：每个页面 0-50 行独有样式

```vue
<!-- Orders.vue -->
<style scoped>
/* 只有这个页面独有的样式：tab-bar、order-mid 等 */
.tab-bar { display: flex; background: #fff; ... }
.order-mid { display: flex; ... }
</style>
```

### 样式行数对比

| 页面 | 改造前 | 改造后 | 减少 |
|------|-------|-------|------|
| Orders.vue | 145 行 | 78 行 | 46% |
| Settings.vue | 180 行 | 56 行 | 69% |
| Security.vue | 158 行 | 31 行 | 80% |
| Favorites.vue | 95 行 | 38 行 | 60% |
| Reviews.vue | 71 行 | 8 行 | 89% |
| Coupons.vue | 82 行 | 50 行 | 39% |
| About.vue | 92 行 | 2 行 | 98% |
| Download.vue | 134 行 | 18 行 | 87% |
| Messages.vue | 261 行 | 165 行 | 37% |

**平均减少 60% 重复样式代码。**

## 已知陷阱（实战中遇到）

### 1. patch 过宽删除 API endpoint

子代理批量替换 loading 弹窗时，若 `old_string` 包含上下文代码（如 `/companion/recommend`），可能误改。

**已发生**: Home.vue 的 `/companion/recommend` 和 `/companion/nearby` 被改为 `/companion/list`。

### 2. 替换误删独立 import

子代理将 `import { showConfirmDialog } from 'vant'` 整行替换时，丢失同文件其他 import。

**已发生**: 
- CompanionRegister.vue 丢失 `useRouter/useRoute`
- Agreement.vue 丢失 `smartBack`

### 3. 重复 import 导致编译失败

子代理多次 patch 同一个文件的 import 时，可能出现重复 `import safeToast`。

**症状**: `[vue/compiler-sfc] Identifier 'safeToast' has already been declared`

**修复**: 删除重复 import。

## 扩展模式：如何应对新需求

**场景**: 客户提出"加一个红色错误提示样式"。

**步骤**:
1. 不在单个页面写 scoped style，而是**先扩展 global.css** 添加 `.error-banner` 类
2. 任何页面都可以用这个类
3. 主题色调整时统一改 global.css

**反模式**:
```vue
<!-- ❌ 错误：在单个页面加 .my-error 类 -->
<style scoped>
.my-error { background: #f44336; color: #fff; ... }
</style>
```

**正确**:
```vue
<!-- ✅ 在 global.css 加新类，所有页面可用 -->
<style>
.error-banner { background: #f44336; color: #fff; padding: 12px; ... }
</style>
```

## 同源参考

- 模式28（主 SKILL.md）：批量改造流程概述
- 模式29：smartBack 路由映射
- 模式30：多 worker CAPTCHA
- 模式31：deploy.sh Nginx 同步