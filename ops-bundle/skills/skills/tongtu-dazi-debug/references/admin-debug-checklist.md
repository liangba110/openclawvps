# 同途搭子管理端调试检查清单

当管理员页面异常时，按此清单逐项排查。

## 1. 数据层

- [ ] curl 调 API 看实际返回数据
- [ ] 对比前端期望字段 vs API 返回字段
- [ ] 检查问题数据的 DB 表 vs API 查询的表是否一致
- [ ] 检查数据是否分布在两个表中需要 UNION/backfill

## 2. 构建层

- [ ] `npm run build` 是否输出 `✓ built in`
- [ ] `dist/` 中是否有 `margin-left: 220px` 等旧 CSS 残留
- [ ] 清除 `dist/` + `node_modules/.vite` 后重建

## 3. 导入检查

- [ ] `<script setup>` 是否包含 `computed`（如果使用了 `computed()`）
- [ ] 是否包含 `safeToast` 导入（如果调用了 `safeToast()`）
- [ ] 是否包含 `safeConfirm` 导入（如果调用了 `safeConfirm()`）
- [ ] 模板中使用的函数如 `smartBack` 是否在 script 中导入或定义

## 4. 样式层

- [ ] 管理端页面 layout: `display: flex` + `flex: 1`（不用 `margin-left`）
- [ ] 全局 CSS `global.css` 中是否有冲突的 `.admin-main` 规则
- [ ] scoped CSS 中是否有 orphaned 属性行

## 5. 路径层

- [ ] 管理端菜单路由是否使用 `sessionStorage` 动态路径
- [ ] 退出登录重定向是否使用动态路径

## 6. 状态同步层

- [ ] 用户提交操作写入哪个表？
- [ ] 管理员查看操作读取哪个表？
- [ ] 如果是不同表，是否有双写逻辑？
