# Global Render Error Handler for Vue SPAs

Place in `App.vue` to catch any child component render error (e.g. lazy-loaded chunk fails to load):

```vue
<script setup>
import { onErrorCaptured } from 'vue'
import safeToast from '@/utils/toast'

onErrorCaptured((err) => {
  console.error('子组件渲染错误:', err)
  safeToast('页面加载出错，建议刷新')
  return false  // prevent default propagation
})
</script>
```

## Key behaviours

- Catches: async component load failures, template errors, missing imports
- Does NOT catch: event handler errors, `setTimeout`/`setInterval` callbacks
- `return false` prevents the error from propagating to the browser console as an unhandled rejection
- Use `safeToast` (not raw `showToast`) because the import chain for `showToast` may itself be broken
- The `console.error` lets developers inspect the real error while users see a friendly message
