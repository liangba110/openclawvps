# SPA Back Navigation: `router.back()` Pattern

**Problem:** Users expect the browser's ← back button to return to the
*previous page they came from*, not a hard-coded fallback route. A common
bug is having a "back" button in an SPA that always navigates to a fixed
route (e.g. `/profile`) regardless of where the user entered from.

## Solution: Prefer `router.back()`, Fallback to Push

```js
// utils/nav.js — shared navigation utilities

import router from '@/router'

export function goBack(fallback = '/') {
  if (window.history.length > 1) {
    router.back()          // returns to previous page
  } else {
    router.push(fallback)  // no history, go to fallback
  }
}
```

## Template Usage

```html
<!-- In any page with a back button -->
<template>
  <div class="header">
    <span class="back" @click="goBack('/profile')">←</span>
    <h1>Page Title</h1>
  </div>
</template>

<script setup>
import { goBack } from '@/utils/nav'
</script>
```

## The Wrong Pattern (Don't Use)

```js
// ❌ This always goes to the same page, ignoring navigation history
export function goBack(fallback = '/') {
  router.push(fallback)
}

// ❌ Map-based approach — fragile, easily misses new routes
const FALLBACK_MAP = {
  '/orders': '/profile',
  '/messages': '/profile',
  // ... every new page needs an entry here
}
export function smartBack(currentPath) {
  for (const [path, fb] of Object.entries(FALLBACK_MAP)) {
    if (currentPath.startsWith(path)) return goBack(fb)
  }
  return goBack('/')
}
```

The map-based approach requires maintaining a mapping of every possible
entry page. It breaks for pages added later (e.g. `/companion/register`
was missing from the map and fell through to `/`).

## When `router.back()` Doesn't Work

- **Direct bookmark / URL entry**: No navigation history exists.
  The fallback route handles this case.
- **In-app redirects**: If the app uses `router.replace()` instead of
  `router.push()`, the previous page may be replaced in history.
  Use `window.history.length > 1` to detect this.
- **Multiple in-app navigations**: If the user navigated through several
  in-app pages, `router.back()` returns through each one in order,
  which is the correct behavior.

## Verification

1. Navigate: Home → Profile → CompanionRegister
2. Click back → should return to Profile
3. Navigate: Home → List → Detail → CompanionRegister
4. Click back → should return to Detail
5. Direct URL open `/companion/register` → back → should go to fallback
