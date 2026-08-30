# 合规弹窗倒计时按钮模式

## 场景

用户首次进入客服/聊天页面时，需阅读合规提醒，按钮在倒计时结束后才可点击。倒计时期间按钮灰色不可用，结束后变为紫色渐变鼓励点击。

## 前端实现（Vue3 + CSS）

### Template

```html
<div class="compliance-overlay" v-if="showCompliance">
  <div class="compliance-modal">
    <div class="cm-icon">⚠️</div>
    <div class="cm-title">【合规重要提醒】</div>
    <div class="cm-text">
      <p>...</p>
    </div>
    <button class="cm-btn" :disabled="countdown > 0" @click="showCompliance = false">
      {{ countdown > 0 ? '请阅读 ' + countdown + '秒' : '我知道了' }}
    </button>
  </div>
</div>
```

### Script

```javascript
const showCompliance = ref(true)
const countdown = ref(3)
const cdTimer = setInterval(() => {
  countdown.value--
  if (countdown.value <= 0) clearInterval(cdTimer)
}, 1000)

onUnmounted(() => { if (cdTimer) clearInterval(cdTimer) })
```

### CSS — 关键样式（按钮状态切换）

```css
/* 禁用态（倒计时中）：灰色不可点 */
.cm-btn {
  width: 100%;
  height: 42px;
  border: none;
  border-radius: 21px;
  font-size: 14px;
  cursor: pointer;
  margin-top: 6px;
  background: #f5f5f5;
  color: #999;
}

/* 可用态（倒计时结束）：紫色渐变 */
.cm-btn:not(:disabled) {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
}
```

## 注意事项

1. **`onUnmounted` 必须清除定时器**，否则组件卸载后定时器仍在运行，触发已销毁的 ref 报错
2. **倒计时秒数**：合规弹窗通常 3-5 秒，确保用户有足够阅读时间
3. **`:disabled` vs `v-if`**：用 `:disabled` 比用 `v-if` 切换两种按钮更简单，CSS 用 `:not(:disabled)` 区分状态
4. **紫色渐变** 使用系统主色 `#667eea→#764ba2`，保持与按钮/标签一致的品牌色
5. 该模式同样适用于：隐私协议确认、付费确认、规则确认等需要强制阅读的场景
