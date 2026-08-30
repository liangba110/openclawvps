# Computed + localStorage Reactivity Trap

## Problem

`computed(() => JSON.parse(localStorage.getItem('user')))` never re-evaluates because
Vue's reactivity system cannot track `localStorage.getItem()` — it's a plain function
call outside Vue's proxy system. After updating localStorage with `setItem()`, the
computed retains its cached value, and the UI never updates.

## Symptom

- API call succeeds, backend confirms data updated
- `localStorage.setItem('user', JSON.stringify(updatedUser))` runs correctly
- But the template still shows the **old** value until page refresh

```js
// ❌ CACHED FOREVER: localStorage is not reactive
const user = computed(() => JSON.parse(localStorage.getItem('user') || '{}'))

function updateGender(gender) {
  await api.put('/user/update', { gender })
  const u = JSON.parse(localStorage.getItem('user') || '{}')
  u.gender = gender
  localStorage.setItem('user', JSON.stringify(u))
  // user.value still shows old gender! ❌
}
```

## Root Cause

Vue 3's `computed()` tracks dependencies via getter interception. `localStorage.getItem`
is a static method — Vue cannot wrap it or detect when its return value changes.
The computed caches on first read and never invalidates.

## Fix: Cache-busting ref

Add a `ref` as a dependency of the computed, then increment it whenever localStorage changes:

```js
// ✅ Cache-busting with version ref
const userVer = ref(0)
const user = computed(() => {
  void userVer.value  // Make computed depend on this ref
  try { return JSON.parse(localStorage.getItem('user') || 'null') || {} }
  catch { return {} }
})

function updateLocal(updates) {
  try {
    const u = JSON.parse(localStorage.getItem('user') || '{}')
    Object.assign(u, updates)
    localStorage.setItem('user', JSON.stringify(u))
    userVer.value++  // Trigger computed re-calculation ✅
  } catch {}
}
```

## Alternative: Direct ref (if localStorage is the sole source)

```js
// Simpler if you don't need computed derivation:
const user = ref(loadFromStorage())
function updateLocal(updates) {
  Object.assign(user.value, updates)
  localStorage.setItem('user', JSON.stringify(user.value))
}
```

But this loses the "auto-read from localStorage on access" behavior that computed provides.

## When This Bites

Any page that:
1. Reads user data via `computed(() => localStorage.getItem(...))`
2. Modifies user data via API calls
3. Expects the UI to refresh without page navigation

Common on Settings pages, Profile pages, and any inline-edit flows.

## One-shot Audit

```bash
grep -rn "localStorage.getItem" src/views/*.vue | grep "computed" 
```
