# Clipboard API — HTTP vs HTTPS Fallback

## Error
```
TypeError: Cannot read properties of undefined (reading 'writeText')
```
Component: Detail, triggered by `navigator.clipboard.writeText()`.

## Root Cause
`navigator.clipboard` is only available in secure contexts (HTTPS or localhost). On HTTP (port 80), `navigator.clipboard` is `undefined`.

## Fix — Two-Tier Fallback

```js
function copyToClipboard(text) {
  if (navigator.clipboard) {
    // HTTPS / localhost — use modern API
    navigator.clipboard.writeText(text).then(() => toast('已复制')).catch(() => toast('复制失败'))
  } else {
    // HTTP fallback — use textarea trick
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'; ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    toast('已复制')
  }
}
```

## Key Rules
1. ALWAYS guard `navigator.clipboard` with existence check before use
2. `document.execCommand('copy')` is deprecated but still works in all browsers
3. The textarea must be appended to DOM, selected, copied, then removed
4. `navigator.share()` (Web Share API) also requires HTTPS — fall back to clipboard