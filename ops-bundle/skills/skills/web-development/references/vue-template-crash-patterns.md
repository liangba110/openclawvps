# Vue Template Silent Crash Patterns

These template expressions look correct but throw at runtime when data is missing, null, or wrong type. Because Vue's `onErrorCaptured` silently swallows these, they manifest as a generic "页面加载出错" toast — not a visible stack trace.

## 1. `String.repeat(NaN)` → RangeError

```html
<!-- ❌ CRASH: score is undefined/null → Math.floor(undefined) = NaN → repeat(NaN) throws -->
{{ '★'.repeat(score) }}
```

```html
<!-- ✅ FIX: coerce to number first -->
{{ '★'.repeat(Number(score) || 0) }}
```

**Files to check:** any component rendering star ratings from API data (List.vue, Detail.vue, Home.vue, Reviews.vue)

## 2. `.toFixed()` on non-number

```html
<!-- ❌ CRASH: rating is a string or null → .toFixed() throws TypeError -->
{{ item.rating.toFixed(1) }}
```

```html
<!-- ✅ FIX: type guard -->
{{ typeof item.rating === 'number' ? item.rating.toFixed(1) : (item.rating || '5.0') }}
```

## 3. `.startsWith()` on null/undefined

```js
// ❌ CRASH: url is null from an API return → .startsWith throws
const fullUrl = url.startsWith('http') ? url : location.origin + url
```

```js
// ✅ FIX: guard first
const fullUrl = (url && typeof url === 'string' && url.startsWith('http')) ? url : location.origin + url
```

## 4. `v-for` over undefined/null

```html
<!-- ❌ CRASH: item.tags is undefined → v-for over non-iterable -->
<span v-for="tag in item.tags" :key="tag">{{ tag }}</span>
```

```html
<!-- ✅ FIX: default to empty array -->
<span v-for="tag in (item.tags || [])" :key="tag">{{ tag }}</span>
```

## 5. `computed` as plain function (template silent fail)

```js
// ❌ BUG: user() is a plain function, not reactive. Template reads user.id → undefined
function user() { return JSON.parse(localStorage.getItem('user') || '{}') }
```

```js
// ✅ FIX: use computed()
const user = computed(() => {
  try { return JSON.parse(localStorage.getItem('user') || '{}') }
  catch { return {} }
})
```

The plain function "works" with no error — but every template access `user.id` returns `undefined`, making `v-if="user.id"` always falsy and all user data invisible.

## 6. `Object.values()` or iteration in computed without null guard

```js
// ❌ CRASH: if someOrder is undefined
const statusText = computed(() => Object.values(statusMap))
```

```js
// ✅ FIX
const list = computed(() => items.value || [])
```

## Systematic Sweep Method

When hunting for these across a large codebase:

1. **Search for `.repeat(`** — every hit in a `.vue` file is a potential crash site
2. **Search for `.toFixed(`** — same
3. **Search for `.startsWith(`** — check if preceded by `&&` or `?.` guard
4. **Search for `v-for=".* in \w+\.\w+"`** — check if the source is always defined
5. **Search for `computed` imports** — verify all `computed` usages are actually `computed()`, not plain functions

Then fix ALL hits in a single pass — the user prefers "一次性完整修复" (one-shot complete fix) over piecemeal debugging.
