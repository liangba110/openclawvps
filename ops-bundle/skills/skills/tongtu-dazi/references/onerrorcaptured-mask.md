# onErrorCaptured 掩盖真实错误 — 调试陷阱

## 问题

Vue 的 `onErrorCaptured` 钩子会捕获所有子组件的渲染错误。如果用它来弹出 Toast「页面加载出错」，会**掩盖真实的 JS 错误**。

## 本项目的实际案例

### 案例1：qrcodejs2 白屏

**真实错误**：`vendor-COcaD4ig.js` 中 qrcodejs2 的 UMD 代码在模块加载时抛出 `Cannot read properties of undefined (reading '_android')`。

**用户看到**：Toast「页面加载出错」出现在页面上，但页面实际是白屏（Vue 没有挂载）。

**误导性**：Toast 暗示「轻度错误，刷新就行」，但实际是 vendor chunk 崩溃导致整个 Vue 应用无法启动。

### 案例2：Login.vue DOM 操作冲突

**真实错误**：`TypeError: Cannot read properties of null (reading 'insertBefore')` — Vue patch 算法遇到空引用节点。

**用户看到**：Toast「页面加载出错」。但页面实际上正常显示，只是扫码功能可能有问题。

**误导性**：Toast 暗示严重错误，但实际上页面功能正常。

## 调试策略

### 白屏时

不要只看 Toast，直接检查控制台：

```bash
browser_navigate(url)
browser_console()  # 看 js_errors 和 console.error 消息
```

- `js_errors: [{message: ""}]` → `Script error.`，通常是模块加载失败或 CORS 问题
- `js_errors: [{message: "Cannot read..."}]` → Vue 运行时错误

### 模块加载错误定位

```bash
# 检查所有 chunk 是否200
for f in $(curl -s "$URL" | grep -oP 'assets/[^"\\'']+\.(js|css)'); do
  curl -sI "$URL/$f" -o /dev/null -w "$f: %{http_code}\n"
done

# 检查 JS 文件 content-type（必须为 application/javascript）
curl -sI "$URL/assets/index-xxx.js" | grep -i content-type

# 检查是否因 crossorigin 导致 Script error.（浏览器静默失败）
curl -s "$URL" | grep -c 'crossorigin'
# >0 且 Nginx 无 CORS 头 → 问题在此
```

### 何时移除 onErrorCaptured

| 阶段 | 建议 |
|------|------|
| 开发/调试 | 保留，但按组件名过滤已知错误 |
| 稳定上线后 | 移除整个 `onErrorCaptured`，让错误自然冒泡到浏览器控制台 |
| 替代方案 | 只在真正需要的地方用 `try/catch` 包裹，不要全局吞错误 |

```javascript
// 推荐：按组件过滤
onErrorCaptured((err, instance, info) => {
  const name = instance?.$?.type?.__name || ''
  const knownIssues = ['SomeKnownBuggyComponent']
  if (knownIssues.includes(name)) return false
  console.error('Unhandled error in', name, err)
  safeToast('操作失败，请重试')
  return false
})
```
