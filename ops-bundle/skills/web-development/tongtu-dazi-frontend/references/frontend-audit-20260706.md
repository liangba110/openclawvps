# 前端全量用户端审计 2026-07-06

审计25个用户端页面，逐页检查：模板渲染崩溃、数据显示缺失、空catch吞错误、全局样式一致性、Layout一致性。

## 汇总

| 严重度 | 数量 |
|--------|------|
| 🔴 高 | 18处空catch静默失败 + 6页完全不使用全局样式 + 1处rating逻辑bug + 1处localStorage无try/catch |
| 🟡 中 | 11页不使用.header-bar + 5页自定义DOM加载 + 2页死代码 + 多处条件判断错位 |

## 逐页问题清单

### 1. Home.vue
- 🔴 空catch: L255 `catch (e) { console.error(e) }` 刷新失败无用户提示; L313 同上初始加载
- 🟡 `randomAge()` 每次render随机年龄，用户会看到年龄跳动
- 🟡 完全不使用全局.page / .header-bar
- 🟡 自定义DOM loading (showLoading/hideLoading)

### 2. List.vue
- 🔴 空catch: L147 `catch (e) { console.error(e) }` loadList失败; L184 同上
- 🟡 使用自定义.gradient-header，非全局.header-bar
- 🟡 自定义DOM loading
- 🟡 L52 `{{ item.order_count }}单` 无??0后备，后端返回null则显示"null单"

### 3. Detail.vue
- 🔴 空catch: L214 `api.post('/coupon/receive', ...).catch(() => {})` 静默吞
- 🟡 自定义DOM loading
- 🟡 不使用.page / .header-bar（自定义.detail-page）

### 4. Orders.vue ✅ 最佳实践
- 🟢 全局样式: .page + .header-bar + .card-3d ✓
- 🟢 全部catch有safeToast ✓
- 🟢 加载/错误/空三态完整 ✓

### 5. CreateOrder.vue
- 🟡 L203 `games.value[0]` 若games为空数组则selectGame(undefined)
- 🟡 L206 catch仅 '加载失败' 无具体原因

### 6. Favorites.vue
- 🟡 L142 catch仅设errorMsg，无console.error
- 🟡 自定义confirm弹窗，未用safeConfirm utility

### 7. Reviews.vue
- 🔴 空catch: L49 `catch(e) { console.error(e) }` 加载失败
- 🔴 rating=0 → 5星: L15 `item.rating || 5` 应为 `item.rating ?? 5`
- 🟡 未使用的 handleBack 函数

### 8. Messages.vue
- 🔴 空catch: L77 `catch (e) { console.error(e) }` 加载失败
- 🟡 无token时直接return，无加载指示

### 9. MessageDetail.vue
- 🔴 空catch: L50 `api.post('/message/read-all').catch(() => {})`
- 🟡 无id时仅显示"消息不存在"，无toast提示

### 10. Settings.vue
- 🔴 空catchx3: L249 `.catch(() => {})`, L261 `catch {}`, L297 `catch {}`
- 🟡 城市输入自动保存无disabled保护

### 11. Security.vue
- 🔴 空catch: L71 `catch {}` 设备列表加载
- 🟡 使用 $router.back() 而非 smartBack

### 12. VerifyIdentity.vue
- 🔴 L108 `JSON.parse(localStorage.getItem('user'))` 无try/catch → 数据坏时整个页面崩溃
- 🔴 不使用.page/.header-bar，自定义.vp-header
- 🟡 step 1弹窗不可关闭（UX问题）

### 13. Coupons.vue
- 🔴 空catch x2: L83-85, L92-95 `catch (e) { console.error(e) }`

### 14. CustomerService.vue
- 🔴 空catch x4: L99 `catch {}` loadHistory, L106 `catch {}` loadMore, L118 `catch {}` FAQ, L143 `catch {}`
- 🟡 v-html XSS风险（formatMsg只替换\n）

### 15. Agreement.vue
- 🟡 自定义DOM loading
- 🟡 safeToast导入但未使用

### 16. About.vue ✅
- 🟢 纯静态，无问题

### 17. Login.vue
- 🔴 空catch: L105 `catch {}` 验证码刷新; L131 `catch (e) {}`
- 🟡 嵌套try/catch (auto-register) 太复杂

### 18. Register.vue
- 🔴 空catch: L85 `catch {}` 验证码刷新

### 19. EmailRegister.vue
- 🔴 空catch: L130 `catch {}` 验证码刷新
- 🟡 死代码: L76 `v-if="false"`; L98-110 showLoading从未调用

### 20. FollowRegister.vue
- 🔴 空catch: L157 `catch {}` 验证码刷新
- 🟡 死代码: L127-138 showLoading从未调用

### 21. CompanionRegister.vue
- 🔴 空catch: L160 `catch(e) { console.error(e) }` 游戏列表; L258 `catch {}` 照片上传
- 🔴 完全不使用任何全局样式类，完全自定义布局

### 22. MyFeedback.vue
- 🔴 空catch: L59 `catch {}` 反馈列表加载完全静默

### 23. Download.vue
- 🔴 空catch: L104 `.catch(() => {})` 备份查询
- 🟡 完全不使用.page/.header-bar（深色自定义页面）

### 24. TeamBoard.vue
- 🔴 空catch: L60 `catch (e) { console.error(e) }` 考勤列表
- 🟡 不使用.page/.header-bar，自定义.page-header无渐变

## 全局样式使用统计

| 页面 | 使用 .page | 使用 .header-bar | 使用 .card-3d | 说明 |
|------|-----------|-----------------|---------------|------|
| Profile | ✅ | ✅ | ✅ | 基准页面 |
| Orders | ✅ | ✅ | ✅ | **最佳实践** |
| Settings | ✅ | ✅ | ✅ | |
| Favorites | ✅ | ✅ | ✅ | |
| Reviews | ✅ | ✅ | ✅ | |
| Messages | ✅ | ✅ | ✅ | |
| MessageDetail | ✅ | ✅ | ✅ | |
| Coupons | ✅ | ✅ | ✅ | |
| Security | ✅ | ✅ | ✅ | |
| Agreement | ✅ | ✅ | ✅ | |
| About | ✅ | ✅ | ❌ | 静态无card-3d |
| Home | ❌ | ❌ | ❌ | 完全自定义 |
| List | ❌ | ❌ | ❌ | 完全自定义 |
| Detail | ❌ | ❌ | ❌ | 完全自定义 |
| VerifyIdentity | ❌ | ❌ | ✅ | |
| Login | ❌ | ❌ | ✅ | 使用全局login-page |
| Register | ❌ | ❌ | ✅ | |
| EmailRegister | ❌ | ❌ | ❌ | 完全自定义 |
| FollowRegister | ❌ | ❌ | ❌ | 完全自定义 |
| MyFeedback | ✅ | ✅ | ❌ | |
| Download | ❌ | ❌ | ✅ | |
| TeamBoard | ❌ | ❌ | ❌ | 完全自定义 |
| CreateOrder | ✅ | ✅ | ❌ | |
| CompanionRegister | ❌ | ❌ | ❌ | 完全自定义 |
| CustomerService | ✅ | ✅ | ❌ | |
