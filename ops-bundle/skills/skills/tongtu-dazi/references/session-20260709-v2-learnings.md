# 2026-07-09 第二波全量审计修复

## 发现并修复的Bug清单

### 安全漏洞
- `admin.py` POST `/api/admin/register` 无 `@admin_required` → 任何人可创建管理员账号
- `playmate_api.py` `except: pass` → 改为 `except Exception: pass`

### 陪玩师订单状态筛选逻辑错误
PlaymateOrders.vue 和 PlaymateHome.vue 的订单筛选与后端 playmate_api.py 的状态校验不一致：
- 后端 accept-order 要求 status=1（已支付）才能接单
- 后端 complete-order 要求 status=2（进行中）才能完成
- 旧筛选：pending=status0(未支付,接不了单), active=status1(待接单,显示进行中)
- 新筛选：pending=status1(可接单), active=status2(进行中), history=status≥3

### CompanionRegister.vue res.code 检查陷阱
axios 拦截器（src/api/index.js:70）返回 `res.data.data`（已解包），因此检查 `res.code !== 0` 永远为 true，所有成功注册都被判为失败。
- 修复：改为检查 `res.companion_id`

### 资源泄漏
- `playmate_api.py` `conn2 = get_connection()` 在 `if 'avatar'` 块内赋值但从未使用/关闭

## 审计检查模式总结
1. 伴随师端所有登录页必须带图形验证码（后端强制校验）
2. 模板中所有 @click 函数必须在 script 中定义（chatWith 缺失）
3. 订单状态值在用户端和陪玩师端语义不同
4. axios 拦截器返回 `res.data.data` → 成功回调中不要检查 `res.code`
5. 修改前端布局（header-bar等）后必须检查 `smartBack`/`useRoute` import 是否补全
