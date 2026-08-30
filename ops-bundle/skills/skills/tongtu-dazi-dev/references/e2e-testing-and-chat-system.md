# E2E 测试与私聊系统参考文档

## 全平台 E2E 截图测试

### 生成测试 token（绕过 captcha）

```python
import sys
sys.path.insert(0, '/opt/ttdazi/backend')
sys.path.insert(0, '/home/ubuntu/.local/lib/python3.12/site-packages')
from app.utils import create_token

token = create_token(user_id, phone)  # phone 可以是邮箱
```

注入到 Playwright browser：
```js
await page.goto('http://host/#/');
await page.evaluate((t) => {
  localStorage.setItem('token', t);
  localStorage.setItem('user', JSON.stringify({id, nickname, ...}));
}, token);
// 然后 reload 页面
await page.reload({ waitUntil: 'networkidle' });
```

### Playwright 截图脚本模式

```js
const { chromium } = require('/home/ubuntu/.npm/_npx/.../playwright');
const fs = require('fs');
(async () => {
  const token = fs.readFileSync('/tmp/token.txt', 'utf-8').trim();
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  
  // 收集控制台错误
  const errors = [];
  page.on('response', r => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url().split('?')[0]}`); });
  
  // 先注入 token
  await page.goto('http://host/#/');
  await page.evaluate((t) => { localStorage.setItem('token', t); }, token);
  
  // 逐页截图
  const pages = ['/#/', '/#/list', '/#/orders', ...];
  for (const url of pages) {
    await page.goto(`http://host${url}`, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `screenshot_${name}.png`, fullPage: true });
  }
  
  // 输出错误汇总
  console.log(JSON.stringify([...new Set(errors)]));
  await browser.close();
})();
```

### 无害错误列表

| 错误 | 原因 | 处理方式 |
|------|------|---------|
| 404 `/uploads/avatars/...` | 用户头像文件已删除但数据库仍引用 | 前端有 fallback 首字头像，不影响 |
| 401 `/api/message/count` | token 过期 | axios 拦截器静默处理并跳转登录 |
| 401 所有 `/api/admin/*` | admin token 过期 | 需要验证码重新登录 |
| 503 `/api/captcha/get` | 瞬发，可重试 | 重试即恢复 |
| 404 `/favicon.ico` | 用 SVG inline 替代，无实际 ico 文件 | 浏览器自动请求，无害 |

### 确认构建成功的方法

不要只看 `deploy.sh` 的 `✅ 前端编译完成`。直接运行：

```bash
npm run build 2>&1 | grep "✓ built in"
# 如果有输出，说明构建成功
# 如果有 "error during build:"，说明构建失败
```

构建失败时检查：
1. `function` 用了 `await` 但没加 `async`
2. 模板缺少 `</template>` 闭合标签
3. `.vue` 文件 CSS 多出 `}` 或 `patch` 写入的字面量 `\n`

## 私聊系统

### 数据库

```sql
CREATE TABLE chat_message (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  from_id INT NOT NULL,
  to_id INT NOT NULL,
  content TEXT NOT NULL,
  is_read TINYINT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_from_to (from_id, to_id),
  KEY idx_to_read (to_id, is_read)
);
```

### 后端 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat/send` | POST | `{to_id, content}` → 发送消息 |
| `/api/chat/messages` | GET | `?user_id=X&page=1` → 获取聊天记录 |
| `/api/chat/conversations` | GET | 会话列表（对方昵称/最后消息/未读数） |
| `/api/chat/unread` | GET | 私聊未读总数 |

注册方式：
```python
from app.chat import chat_bp
app.register_blueprint(chat_bp)
```

### 前端页面

| 路由 | 组件 | 功能 |
|------|------|------|
| `/chat` | `ChatConversation.vue` | 对话页：气泡 + 5s 轮询 |
| `/chat-list` | `ChatList.vue` | 会话列表 |

### 关键实现细节

1. **不要用 `encodeURIComponent`**：Vue Router 自动编码 query 参数，双重编码导致乱码
2. **companion_user_id**：订单 API 需要 `c.user_id as companion_user_id`（陪玩师表 user_id），不是 `companion_id`（陪玩师表主键）
3. **chat-row 必须放在 v-for 循环内**：不在循环内的 chat-row div 不会被渲染
4. **chatWithCompanion 函数必须在 script 中定义**：只在 template 中引用但未定义函数会静默失败（不报错也不渲染）
