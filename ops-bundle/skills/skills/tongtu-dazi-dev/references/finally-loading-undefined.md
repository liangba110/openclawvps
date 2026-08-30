# Vue `finally` 中 `loading.value` 未定义导致页面崩溃

## 症状

页面正常加载数据后瞬间白屏/崩溃，控制台报 `ReferenceError: loading is not defined`。

## 根因

组件模板中没有 `loading` 状态（`v-if="loading"` 等），但 `onMounted` 中写了：

```js
finally { loading.value = false }
```

`loading` 变量从未用 `ref()` 声明。ES Module strict 模式下抛出 ReferenceError。

## 案例

**CreateOrder.vue**（2026-07-16 修复）：
```js
// ❌ 崩溃
onMounted(async () => {
  // ... 加载数据 ...
  } catch {}
  finally { loading.value = false }  // loading 未定义！
})

// ✅ 修复
onMounted(async () => {
  // ... 加载数据 ...
  } catch {}
  // 删除 或 添加: const loading = ref(true)
})
```

## 排查

```bash
# 搜索所有 finally 引用了 loading 但没有声明的文件
grep -rn "finally.*loading" frontend/src/ --include="*.vue" \
  | grep -v "const loading\|let loading\|loading = ref"
```

## 预防

- `finally` 块中操作的变量必须在块外声明
- 如果不需要 loading 状态，直接删除 `finally` 块
- 使用 `try/catch` 而非 `try/catch/finally` 除非确实需要清理逻辑
