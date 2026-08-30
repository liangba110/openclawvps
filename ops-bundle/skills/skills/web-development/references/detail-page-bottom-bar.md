# Detail Page Bottom Action Bar Pattern

When a detail/profile page needs its own fixed bottom action bar (e.g., "聊一聊" + "立即对接") while the app has a global bottom tab navigation:

## Option A: Hide the app's tab nav

Add the page route to `noTabBarPages` in `App.vue`:

```javascript
const noTabBarPages = ['/login', '/detail']  // add '/detail'
```

Then the page's bar can use `position: fixed; bottom: 0`.

## Option B: Show both (bar above nav)

Keep the app tab nav visible and position the page-level bar above it:

```css
.page-bar {
  position: fixed;
  bottom: 64px;        /* app tab nav height */
  left: 0;
  right: 0;
  z-index: 99;
  height: 52px;
}
```

Add matching bottom padding to the page content to prevent the bar from covering content:

```css
.page-content {
  padding-bottom: calc(52px + 64px);  /* bar height + nav height */
}
```

## Common pitfalls

- **Vue scoped CSS**: If the bar doesn't render, check that all template content is inside a single root `<div>`. Vue's scoped CSS only assigns `data-v-xxx` attributes to descendants of the root element. A sibling element won't get the attribute.
- **Old chunk files**: After many builds, old hashed chunk files accumulate on the server. The browser may load a stale version. Clean the assets directory periodically with `rsync --delete`.
- **App nav height**: Measure the app's `.bottom-nav { height }` — typically `64px` but can vary. The page-level bar's `bottom` must match this value exactly.
