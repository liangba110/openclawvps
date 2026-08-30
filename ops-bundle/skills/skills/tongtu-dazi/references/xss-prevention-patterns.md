# XSS 防护模式

## v-html / innerHTML XSS 漏洞

### 症状
用户提交的文本内容（聊天消息、公告等）通过 `v-html` 或 `innerHTML` 渲染时，内含 `<script>` 标签会被执行。

### 根因
`formatMsg()` 函数只做了 `\n → <br>` 替换，未进行 HTML 实体转义，用户可提交 `alert('xss')`。

### 修复

**前端（Vue）：**
```javascript
function formatMsg(text) {
  if (!text) return ''
  // HTML 实体转义防 XSS，然后在安全的字符上做换行
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
  return escaped.replace(/\n/g, '<br>')
}
```

**后端（Python）：**
```python
import re
content = re.sub(r'<[^>]*>', '', content)
```

### 排查清单

| 文件 | 风险类型 | 修复状态 |
|------|---------|---------|
| `CustomerService.vue` | `v-html="formatMsg(msg.content)"` | ✅ 已修复（HTML转义） |
| `Agreement.vue` | `v-html="content"`（后端返回内容） | 🟡 低风险（管理员可控） |
| `chat.py` send() | 用户提交的 聊天消息 | ✅ 已修复（re.sub 过滤） |

### 预防
1. 所有 `v-html` 的输入源必须是**后端返回的受控内容**（如管理员编辑的协议文本）
2. 用户输入 → 显示场景 → 用 `{{ text }}` 插值而非 `v-html`
3. 必须用 `v-html` 保留换行/富文本时 → `formatMsg()` 先转义再放行特定标签
