# 在线客服系统完整架构

## 数据库

```sql
-- 消息表
CREATE TABLE customer_service (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    content TEXT NOT NULL,
    faq_log_id INT UNSIGNED DEFAULT NULL,
    is_admin TINYINT NOT NULL DEFAULT 0,
    is_read TINYINT NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id)
);

-- FAQ 学习表（含多级类目）
CREATE TABLE faq_log (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    question TEXT NOT NULL,
    question_hash CHAR(32) NOT NULL,
    category VARCHAR(50) DEFAULT NULL,
    subcategory VARCHAR(50) DEFAULT NULL,
    reply TEXT,
    reply_admin_id INT UNSIGNED DEFAULT NULL,
    count INT UNSIGNED DEFAULT 1,
    status TINYINT NOT NULL DEFAULT 0,  -- 0=待审核, 1=已采纳, 2=已忽略
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_hash (question_hash),
    INDEX idx_status (status),
    INDEX idx_category (category)
);
```

## 后端 API（/api/cs/）

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| /send | POST | user | 发送消息（含自动匹配FAQ） |
| /history | GET | user | 分页获取历史（page/page_size/total） |
| /faq | GET | none | FAQ快捷问题列表（按类目分组） |
| /unread-count | GET | user | 未读客服消息数 |
| /admin/users | GET | admin | 有消息的用户列表+未读数 |
| /admin/conversation/<uid> | GET | admin | 与某用户的对话 |
| /admin/reply | POST | admin | 回复用户（自动触发FAQ学习关联） |
| /admin/unread-total | GET | admin | 全局未读消息数 |
| /admin/faq/pending | GET | admin | 待审核FAQ(出现≥2次，按类目排序) |
| /admin/faq/approved | GET | admin | 已采纳FAQ |
| /admin/faq/approve/<id> | POST | admin | 审核通过 |
| /admin/faq/reject/<id> | POST | admin | 忽略 |
| /admin/faq/update/<id> | POST | admin | 修改回复并采纳 |

## FAQ 自动回复 + 学习流程

```
用户发送消息(/api/cs/send)
    ↓
1. 静态关键词匹配（10组关键词）
   → 命中：插入 is_admin=1 消息，直接返回
    ↓ 未命中
2. 动态 FAQ 匹配（faq_log 表 status=1 且 reply IS NOT NULL，按 question_hash）
   → 命中：增加 count 计数，返回自动回复
    ↓ 未命中
3. log_unmatched() → _classify() 自动归类 → 写入 faq_log（MD5 去重合并 count）
   → 问题出现 ≥2 次后出现在 admin/faq 待审核列表
    ↓
4. 管理员回复时 → log_admin_reply() → 查找对应 question_hash → 关联回复到 faq_log
    ↓
5. 管理端审核（/admin/faq） → 采纳/更新/忽略
   → 采纳后 status=1，自动加入匹配引擎
```

## 多级类目自动归类

### 类目体系（7大类 18子类）

| 一级类目 | 二级子类 | 匹配关键词 |
|----------|---------|----------|
| 充值与支付 | 充值流程/支付方式/退款 | 充值/微信支付/退款/退钱 |
| 订单服务 | 下单流程/服务时长/取消订单 | 预约/1小时/取消 |
| 陪玩师 | 注册申请/审核进度/收入提现/接单技巧 | 注册/审核/提现/接单 |
| 账户安全 | 密码修改/手机绑定/账号封禁 | 密码/绑定/封号 |
| 投诉建议 | 投诉陪玩师/举报用户/功能建议 | 投诉/举报/建议 |
| 其他 | 联系方式/常见问题 | 电话/微信/在吗/hi |

### 实现

```python
CATEGORY_MAP = [
    # (category, subcategory, [keywords])
    ("充值与支付", "退款", ["退款", "退钱", "退单"]),
    ("陪玩师", "注册申请", ["注册", "申请", "成为陪玩师"]),
    ...
]

def _classify(text: str):
    t = text.lower()
    for cat, sub, keywords in CATEGORY_MAP:
        for kw in keywords:
            if kw in t:
                return cat, sub
    return "其他", "其他问题"
```

### 前端展示

- `get_faq_list()` 返回 `[{category, items: [{id, title, desc}]}]` 分组结构
- 用户端：按类目折叠面板展示（`faq-cat-group`）
- 管理端：每个问题卡片显示类目标签（`faq-tag`），按类目排序
- 用户发送消息时 `log_unmatched()` 自动调用 `_classify()` 写入 category/subcategory

### 添加新类目

只需在 `CATEGORY_MAP` 中添加元组即可，无需修改数据库或前端。后续问题自动纳入对应类目。

## 前端智能轮询

| 阶段 | 间隔 | 触发条件 |
|------|------|---------|
| 活跃 (0-2min) | 3秒 | 最近交互 2 分钟内 |
| 低活跃 (2-5min) | 15秒 | 无交互 2-5 分钟 |
| 超时 (5min+) | 停止 | 5 分钟无活动 |

- `lastActivity = Date.now()` 在发送消息/收到新回复时重置
- 管理端：选中用户才轮询，5分钟超时显示"⏸ 已暂停刷新"，按钮恢复
- 用户列表：独立 10 秒轻量刷新（仅拉用户列表和未读数）

## 安全性

- 所有用户端点需 @login_required
- 管理端点需 @admin_required
- 消息长度限制 500 字
- 防重复自动回复：内存 Set 记录最近 100 条已回复消息 ID

## 文件

| File | Purpose |
|------|---------|
| `backend/app/customer_service.py` | REST API + 辅助函数 |
| `backend/app/faq.py` | 关键词匹配 + 动态学习 + 类目归类 |
| `frontend/src/views/CustomerService.vue` | 用户端聊天（FAQ按类目展示+智能轮询） |
| `frontend/src/views/admin/AdminService.vue` | 管理端客服面板 |
| `frontend/src/views/admin/AdminFaq.vue` | FAQ 学习管理面板 |

## 为什么不使用 WebSocket

Flask-REDACTED + gunicorn sync workers 有已知问题：
1. MySQL Decimal 类型无法 JSON 序列化 → `TypeError: Object of type Decimal is not JSON serializable` → worker crash
2. `socketio` 对象在 `create_app()` 内创建，gunicorn 需要模块级变量
3. 改为 `main:socketio` 后 Decimal 崩溃仍导致 worker 死亡

当前规模下 REST 3 秒轮询足够稳定。详见 `references/websocket-decimal-crash.md`。
