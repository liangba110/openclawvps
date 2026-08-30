# Vite manualChunks — Cross-Chunk Dependency Pitfall

## Problem

Using `build.rollupOptions.output.manualChunks` with **directory-based rules**
can cause shared utility functions to be placed into page-specific chunks,
creating runtime import errors:

```js
// BAD: matches ANY file under src/views/admin/
if (id.includes('src/views/admin/')) return 'admin-pages'
```

When a shared utility (e.g. `safeToast` in `utils/toast.js`) is imported by
both admin pages AND non-admin pages (like EmailRegister), Rollup may place
the utility into one of the page-specific chunks. Non-admin pages then try
to import from the admin-pages chunk — which hasn't been loaded yet.

## Symptom

Lazy-loaded pages throw an error or show blank screens when navigating to
them. The browser console shows a chunk loading error (404 or module not
found).

## Root Cause

Rollup's code splitting places shared dependencies into the first chunk that
references them. With `manualChunks` directory rules, a utility imported by
both admin and non-admin code may end up in the admin chunk. When the
non-admin page is lazy-loaded, it tries to import from the unloaded admin
chunk.

## Fix: Split Only Libraries, Not Pages

Vite's dynamic `import()` already creates per-route chunks automatically.
`manualChunks` should only split **third-party libraries**, not app code:

```js
// GOOD: only split node_modules
build: {
  rollupOptions: {
    output: {
      manualChunks(id) {
        if (id.includes('node_modules/echarts')) return 'echarts'
        if (id.includes('node_modules/vant')) return 'vant'
        if (id.includes('node_modules/vue') || id.includes('node_modules/@vue') || id.includes('node_modules/vue-router')) return 'vue-core'
        if (id.includes('node_modules')) return 'vendor'
        // Do NOT add app-level directory rules here
      }
    }
  }
}
```

## Verification

After building, check that no lazy-loaded chunk imports from another
page-specific chunk:

```bash
node -e "
const fs = require('fs');
const f = fs.readdirSync('dist/assets').find(f => f.startsWith('EmailRegister-') && f.endsWith('.js'));
const code = fs.readFileSync('dist/assets/' + f, 'utf-8');
console.log('Imports admin-pages:', code.includes('admin-pages'));
"
```

All should print `false`.
