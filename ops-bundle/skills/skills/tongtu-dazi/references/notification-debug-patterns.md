# 推送通知系统调试模式

当用户报告"推送失败"时，按以下流程系统排查，不要局部修。

## 信号检查（判断推送到哪个阶段失败了）

用户在网页上"看不到推送"可能指：

| 信号 | 真实问题 | 排查重点 |
|------|---------|---------|
| "通知收不到" | 后端未创建通知记录 | 检查 API 端点是否被调用、send_notification 是否执行 |
| "红点不显示" | 前端 message/count 轮询失败 | 检查 App.vue 的 fetchUnread() 和 axios 拦截器 |
| "消息列表空白" | message/list API 错误或前端渲染报错 | 检查 API 返回格式 + Vue 模板渲染 |
| "点了通知没反应" | MessageDetail.vue 组件缺失或路由问题 | 检查 router/index.js 和 views/MessageDetail.vue |
| "某些场景通知不到" | 特定流程的 send_notification 未执行（如确认完成通知） | 检查对应流程的代码路径 |

## 标准排查流程

### 第一步：检查后端日志

```bash
sudo journalctl -u ttdazi --no-pager -n 100 | grep -i "Traceback\|Error\|NameError\|OperationalError"
```

**常见发现：**
- `Unknown column 'score' in 'field list'` → 查错了表（见下方模式）
- `send_notification` 未执行 → 调用它的函数在之前就报错退了（如 SQL 错误）

### 第二步：直接测试 API

```bash
# 生成测试 token
PYTHONPATH="/opt/ttdazi/backend" python3.12 -c "
from app.utils import create_token
t = create_token(10001, '13800138000')
with open('/tmp/token.txt','w') as f: f.write(t)
print(t[:30]+'...')
"

TOKEN=$(cat /tmp/token.txt)

# 测试消息列表
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5002/api/message/list \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(f'code={d[\"code\"]}, count={len(d.get(\"data\",[]))}')"

# 测试未读计数
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5002/api/message/count
```

### 第三步：测试完整订单通知链路

```bash
# 1. 下单
curl -s -X POST http://127.0.0.1:5002/api/order/create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"companion_id":23,"game_id":1,"service_type":1}'

# 2. 检查双方通知是否生成（分别用下单用户和陪玩师user_id的token）
curl -s -H "Authorization: Bearer $USER_TOKEN" http://127.0.0.1:5002/api/message/list \
  | python3 -c "import sys,json;d=json.load(sys.stdin);[print(f'  [{m[\"id\"]}] {m.get(\"icon\",\"\")} {m.get(\"title\",\"\")[:30]}') for m in d.get('data',[])[:3]]"
```

### 第四步：检查前端组件完整性

```bash
# 路由引用的组件文件是否存在
grep 'component.*views/' src/router/index.js | while read line; do
  file=$(echo "$line" | grep -oP "(?<=@/views/)[^']+")
  if [ ! -f "src/views/$file" ]; then
    echo "⚠️ 路由引用的组件不存在: src/views/$file"
  fi
done
```

## 常见通知失败模式

### 模式 A: `send_notification` 调用前的 SQL 报错导致通知"静默丢失"

**根因：** send_notification 调用之前的 SQL 查询有错（如查错表/漏列），函数提前 500 返回，后面的 send_notification 永远不执行。

**症状：** 用户说"支付后没收到通知" → 检查日志发现 SQL Error 在 UPDATE 阶段，send_notification 从未被调用。

```python
# ❌ 上下游依赖：SQL 报错 → 函数 return fail(...) → 通知不执行
def pay():
    cur.execute("SELECT fake_column FROM companion WHERE id=%s", (cid,))  # ← Error！
    # ...
    send_notification(...)  # ← 永远执行不到
```

**排查：** 在 send_notification 调用之前的所有数据库操作中，逐一检查 SELECT 的列名和表名。

### 模式 B: 查错表（同类型陷阱）

**核心案例：** `SELECT score FROM companion WHERE id=%s`
- `score` 列在 `user` 表，不在 `companion` 表
- `companion` 表有 `credit_score` 但不是 `score`

**类似模式（已记录在 SKILL.md）：**
- `SELECT nickname FROM companion`  — nickname 在 user 表
- `SELECT score FROM companion`     — score 在 user 表（本会话新增）
- `SELECT avatar FROM companion`    — avatar 在 user 表

**排查规则：** 查询 `companion` 表时，只有以下列存在：`id, user_id, game_id, rank_title, price_1h/2h/night, intro, is_online, status, tags, life_photos, max_hours_per_day, total_income, total_orders, credit_score, badges, account_name, alipay_account`。
其他字段（`nickname, avatar, score, phone, email, gender, city, verify_status`）都在 `user` 表，必须 JOIN。

### 模式 C: 路由指向了不存在的组件文件

**根因：** `router/index.js` 中 `import('@/views/MessageDetail.vue')` 注册了路由，但是 `src/views/MessageDetail.vue` 文件从未被创建。

**症状：** 点击通知列表 → 路由跳转 → 空白页（SPA 不报 404，用户看到白屏或 loading 卡死）

与已有的"新页面路由注册必查"陷阱是反向关系——那个是文件存在但路由没加，这个是路由存在但文件缺失。**两种都要检查。**

**排查命令：**
```bash
# 路由有的组件，文件是否存在（反向检查）
grep -oP "(?<=@/views/)[^']*\.vue" router/index.js | sort -u | while read f; do
  [ ! -f "src/views/$f" ] && echo "⚠️ 缺失: src/views/$f"
done
```

### 模式 D: 同一个通知场景发送两次

**根因：** 补丁或重构时，同一事件的 `send_notification()` 被放在两个不同的 return 分支中，用户收到重复通知。

**排查：** 搜索同一 ntype+title 组合出现在多个文件中，确认只有一个路径会执行到。

## 验证清单（修完通知系统后必须做）

- [ ] `curl /api/message/list` 返回 code=0 和数据
- [ ] `curl /api/message/count` 返回正确的 unread_count
- [ ] 陪玩师的用户和下单用户**都**能收到通知（双端验证）
- [ ] 后端日志 `journalctl -u ttdazi | grep -i traceback` 无匹配
- [ ] 点击通知跳转到 MessageDetail 页面正常（非空白页）
- [ ] 底部导航「消息」Tab 显示红点（App.vue badge）
