# Polling Timer Crash — `Cannot create property '_slow' on number`

## Error Transcript

```
TypeError: Cannot create property '_slow' on number '10'
    at startPolling (AdminService.vue)
    at selectUser (AdminService.vue)
```

## Root Cause

`setInterval()` returns a **number** (timer ID). JavaScript primitives cannot have custom properties.

```js
// ❌ BROKEN
timer = setInterval(() => { ... }, 3000)
const slow = setInterval(() => { ... }, 15000)
timer._slow = slow  // TypeError: Cannot create property '_slow' on number '10'
```

The number `10` is the timer ID returned by `setInterval()`. Even though `typeof timer === 'number'`, you can't add `._slow` to it.

## Fix

Use separate variables for each timer:

```js
let timer = null
let slowTimer = null  // separate variable, NOT a property of timer

function startPolling() {
  stopPolling()
  timer = setInterval(() => { ... }, 3000)
  slowTimer = setInterval(() => { ... }, 15000)
}

function stopPolling() {
  if (timer) { clearInterval(timer); timer = null }
  if (slowTimer) { clearInterval(slowTimer); slowTimer = null }
}
```

## Why This Happens

| Language | Timer API | Return Type | Property Assign |
|----------|-----------|-------------|-----------------|
| Node.js | `setInterval` | `Timeout` object | ✅ Works (`timer._slow = ...`) |
| Browser | `window.setInterval` | `number` | ❌ TypeError |

Vue runs in the browser, so `setInterval` returns a number. Always use separate variables for multiple timers.
