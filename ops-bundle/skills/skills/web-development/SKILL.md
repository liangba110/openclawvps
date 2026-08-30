---
name: web-development
description: Use when users need to implement, integrate, debug, build, deploy, or validate a Web frontend after the product direction is already clear, especially for React, Vue, Vite, browser flows, or CloudBase Web integration.
version: 2.23.2
alwaysApply: false
---

## Standalone Install Note

If this environment only installed the current skill, start from the CloudBase main entry and use the published `cloudbase/references/...` paths for sibling skills.

- CloudBase main entry: `https://cnb.cool/tencent/cloud/cloudbase/cloudbase-skills/-/git/raw/main/skills/cloudbase/SKILL.md`
- Current skill raw source: `https://cnb.cool/tencent/cloud/cloudbase/cloudbase-skills/-/git/raw/main/skills/cloudbase/references/web-development/SKILL.md`

Keep local `references/...` paths for files that ship with the current skill directory. When this file points to a sibling skill such as `auth-tool` or `web-development`, use the standalone fallback URL shown next to that reference.

**Cross-cutting protocols** (required before code changes or static hosting publish):
- Change Safety Protocol: `https://cnb.cool/tencent/cloud/cloudbase/cloudbase-skills/-/git/raw/main/skills/cloudbase/references/cloudbase-platform/references/protocols/change-safety-protocol.md`
- Deployment Gate: `https://cnb.cool/tencent/cloud/cloudbase/cloudbase-skills/-/git/raw/main/skills/cloudbase/references/cloudbase-platform/references/protocols/deployment-gate.md`

# Web Development

## Activation Contract

### Use this first when

- The request is to implement, integrate, debug, build, deploy, or validate a Web frontend or static site.
- The design direction is already decided, or the user is asking for engineering execution rather than visual exploration.
- The work involves React, Vue, Vite, routing, browser-based verification, or CloudBase Web integration.

### Read before writing code if

- The task includes project structure, framework conventions, build config, deployment, routing, or frontend test and validation flows.
- The request includes UI implementation but the visual direction is already fixed; otherwise read `ui-design` first.

### Then also read

- General React / Vue / Vite guidance -> `frameworks.md`
- Browser flow checks or page validation -> `browser-testing.md`
- Login flow -> `../auth-tool/SKILL.md` (standalone fallback: `https://cnb.cool/tencent/cloud/cloudbase/cloudbase-skills/-/git/raw/main/skills/cloudbase/references/auth-tool/SKILL.md`), then `../auth-web/SKILL.md` (standalone fallback: `https://cnb.cool/tencent/cloud/cloudbase/cloudbase-skills/-/git/raw/main/skills/cloudbase/references/auth-web/SKILL.md`)
- Official Account JSAPI Pay, Native QR-code Pay, or WeChat OAuth on CloudBase -> `../cloudbase-wechat-integration/SKILL.md` (standalone fallback: `https://cnb.cool/tencent/cloud/cloudbase/cloudbase-skills/-/git/raw/main/skills/cloudbase/references/cloudbase-wechat-integration/SKILL.md`; official docs: `https://docs.cloudbase.net/integration/introduce/index.md`)
- CloudBase database work -> matching database skill

### Do NOT use for

- Visual direction setting, prototype-first design work, or pure aesthetic exploration.
- Mini programs, native Apps, or backend-only services.
- WeChat payment or Official Account OAuth contract details; use `cloudbase-wechat-integration` after identifying the Web surface.

### Common mistakes / gotchas

- Starting implementation before clarifying whether the task is design or engineering execution.
- Mixing framework setup, deployment, and CloudBase integration concerns into one vague change.
- Treating cloud functions as the default solution for Web authentication.
- Skipping browser-level validation after a UI or routing change.
- **History mode SPA with CloudBase static hosting**: deploying a single-page app using History mode (React Router / Vue Router) without configuring the static hosting "404 error document" to `index.html`. This causes `NoSuchKey` / 404 errors when users refresh or directly visit any sub-route.
- **Vant UI blank toasts**: Two root causes. (1) Missing `showToast` import after migration to `safeToast` -- the Vue SFC compiler won't warn. Grep dist for remaining `showToast(`. (2) Vant 4 toast singleton race condition: `closeToast()` followed immediately by a new toast creates a blank overlay because close is async with exit animations. The best fix for login/forms is to remove Vant loading entirely -- use the button `:disabled` state + `loading.value` to toggle text, and call `safeToast` directly for results. See `references/vant-toast-safety.md`.
- **`import { reactive, computed, watch }` missing in `<script setup>`**: Adding `reactive({})`, `computed(() => ...)`, or `watch(() => ...)` requires adding the named export to the `import` line. Vite builds succeed but the component throws `ReferenceError` at runtime. Always check browser console when investigating page loading errors.
- **Axios FormData upload silently fails**: Axios default `Content-Type: application/json` overrides the browser's automatic `multipart/form-data; boundary=...` header. The backend receives JSON instead of file data. Fix: move `Content-Type` out of defaults, conditionally `delete config.headers['Content-Type']` when `config.data instanceof FormData` in the request interceptor. See `references/axios-formdata-upload.md`.
- **Backend MySQL type mismatch with frontend strings**: Database columns like `gender TINYINT` or `status TINYINT` store integers but frontend sends/receives strings ('male', 'pending'). `pymysql.err.DataError: (1366)` at 500. Fix: backend must map both directions (int->string on read, string->int on write). Always fix in backend, never frontend-only. Search ALL return sites (login, register, profile, admin list). See `references/backend-db-type-mismatch.md`.
- **Dual `conn.close()` in paired try/finally blocks**: When the same database connection variable is closed in a first `finally` block, then reused in a second block for DB updates, the connection is already closed -> `pymysql.err.Error: Already closed`. Fix: use a NEW connection variable (`db = get_connection()`) for the second block, or restructure to a single try/finally.
- **computed + localStorage reactivity**: `computed(() => JSON.parse(localStorage.getItem('user')))` never re-evaluates because Vue can't track `localStorage` changes. After `setItem()`, the UI still shows old data. Fix: add a cache-busting `ref` (`userVer.value++`) as a dependency. See `references/computed-localstorage-reactivity.md`.
- **Vue 3 template — `sessionStorage`/`localStorage` NOT accessible in template expressions**: In Vue 3 SFC templates, `sessionStorage` is NOT a built-in global. The template compiler resolves it as a component property, which returns `undefined`. Using `sessionStorage.getItem('key')` directly in `@click` or `:class` bindings causes `Cannot read properties of undefined` errors. `window.sessionStorage` also fails — Vue resolves `window` as a component property too. **Fix**: always read browser globals in `<script setup>` and assign to a const, then reference that const in the template. Example:
  ```vue
  <script setup>
  const adminPath = sessionStorage.getItem('admin_route_path') || 'default-path'
  </script>
  <template>
    <div :class="{ active: isActive(`/${adminPath}/users`) }">...</div>
  </template>
  ```
  See `references/admin-layout-and-routing.md` for the full admin path rotation pattern.
- **Vite manualChunks cross-dependency**: Splitting app code by directory (`src/views/admin/` -> `admin-pages`) causes shared utilities to end up in page-specific chunks, breaking lazy-loaded pages that import them. Only split `node_modules` in `manualChunks`. Vite's dynamic `import()` already creates per-route chunks. See `references/vite-chunk-splitting.md`.
- **Gunicorn multi-worker shared state**: in-memory Python dicts like `_verify_codes = {}` are NOT shared across gunicorn workers. Each worker has its own process. Use the database (MySQL/Redis) for verification codes, rate limits, captcha answers, or any cross-request state that must survive worker restarts. See `references/captcha-multiworker-fix.md` for the captcha-specific fix pattern.
- **Vue Router `encodeURIComponent` double-encoding in query params**: `router.push({ path: '/chat', query: { name: encodeURIComponent(val) } })` causes double-encoding because Vue Router auto-encodes query parameter values. `encodeURIComponent` encodes once, then Vue Router encodes again. Fix: pass raw string values (e.g., `router.push({ path: '/chat', query: { name: rawName } })`); Vue Router handles encoding.
- **Vite silent build failure — unrelated Vue SFC syntax error blocks all output**: When Vite encounters a syntax error in ANY `.vue` file (e.g., `function completeDemand(d) { await ... }` missing `async`, or orphaned CSS outside a block), the entire build fails silently for ALL pages. The error message appears in the build log (search for `error during build:`), but if the deploy script only checks the last 3 lines, it looks like success. Always check the full build log for `error during build:` before declaring deployment complete. Fix: `npm run build 2>&1 | grep -E 'error during build|✗ Build failed|Build failed'`. **deploy.sh masks failures**: a failed build produces `✅ 前端编译完成` if the last echoed line matches. Never trust deploy output alone — grep for `error during build` or `✗ Build failed` in the raw build log. When build fails, check the flagged file around the reported line with `read_file` — the actual problem may be a few lines before or after.
- **Vite build accumulation on deployment server**: Each Vite build produces uniquely-hashed chunk files. Over many build-deploy cycles, OLD chunk files accumulate on the server. The browser can load a cached old file, causing features to appear missing even after a fresh deploy. **Fix**: periodically clean the deployment target's assets directory before syncing, or use `rsync --delete` to mirror only the current build output.
- **Vue 3 scoped CSS — only the root element's descendants get data attributes**: In Vue 3 SFC `<style scoped>`, CSS selectors are rewritten with `[data-v-xxxxx]` attribute selectors. These data attributes are only applied to the **root component element and its descendants** — NOT to sibling elements at the root level. A template with two siblings will have the sibling class selector rewritten but no matching data attribute on the element, so the CSS never applies. **Fix**: always wrap all template content in a single root `<div>`, including any fixed-position bottom bars. Use a non-scoped `<style>` block for elements that must be siblings.
- **App bottom navigation conflict with page-level fixed bars**: When a page uses `position: fixed; bottom: 0` for its own action bar, it overlaps with the app's main bottom tab bar. **Two fix options**: (1) Add the page's route path to the `noTabBarPages` array in `App.vue` to hide the app tab nav on that page. (2) If the app tab nav should remain visible, set `bottom: <nav-height>` (typically `64px`) on the page-level bar so it sits above the navigation, with a matching `padding-bottom` on the page content. See `references/detail-page-bottom-bar.md`.
- **Vue SFC `function` vs `async function` in `<script setup>`**: `<script setup>` does not wrap function bodies in `async` context. Any `function` that uses `await` must be explicitly `async function`. The error message `Unexpected reserved word 'await'` points to the correct location but may be misleading if the line number refers to a different section of the file.
- **Backend API testing bypass for captcha-protected endpoints**: When captcha blocks automated API testing, generate a JWT token directly: `python3.12 -c "import sys; sys.path.insert(0, '/opt/ttdazi/backend'); from app.utils import create_token; print(create_token(user_id, phone))"`. This bypasses login+captcha entirely. The token is valid for the configured JWT expiry time.
- **Vue 3 `<script setup>` TDZ -- `watch`/`onMounted` before `const` declaration**: `watch(() => route.path, ...)` called before `const route = useRoute()` throws `ReferenceError: Cannot access 'route' before initialization`. `<script setup>` runs top-to-bottom -- `const` has temporal dead zone. **Always declare `route`/`router`/all refs FIRST**, then lifecycle hooks and watchers that reference them.
- **Vue CSS design system -- define global classes in `global.css` to avoid duplicating scoped styles**: Rather than each page redefining `.header-bar`, `.card`, `.btn-primary`, etc., add these as global CSS classes once. Pages reference through `class="page header-card btn-primary input-field"`. See `references/vue-css-design-system.md`.
  - **3D card effect**: Use `.card-3d` instead of `.card` for a unified 3D floating card with multi-layer shadows, perspective rotation (`rotateX`/`rotateY`), and active-state press feedback. See the reference for full CSS.
  - **`.mi-arrow` wrapper pitfall**: The `.mi-arrow` arrow uses `margin-left: auto` to push to the right. It MUST be a direct child of `.menu-item-3d`, NOT wrapped in a nested `<div>`. A wrapper like `<div class="mi-arrow-group">` breaks the auto-margin calculation -- the arrow stays stuck to the text instead of the right edge.
  - **`.card-3d` on `<button>` elements**: Never put `class="card-3d"` on a `<button>`. The 3D `rotateX`/`rotateY` transform and `::before` pseudo-element conflict with button semantics. Use independent styles (e.g., `.logout-btn { background: #fff; border-radius: 12px; color: #f44336; }`).
  - **Card stacking without gap**: `.card-3d` has no margin. Stacked cards (e.g., in Settings.vue) need a flex container with `gap: 14px`. Never use negative margins on child headers (`.menu-section-title { margin: -14px -16px }`) to "fill the card" -- that causes overlap between cards. Use `padding: 0 0 10px` inside the card.
  - **Login/register page sharing**: Login, Register, EmailRegister, FollowRegister can all share `.login-page`/`.login-card`/`.login-tabs`/`.login-logo`/`.login-agreement` global classes. Their `scoped` style only needs captcha-row and send-code-btn.
- **Axios 401 interceptor -- HTTP status 401 goes to `err` callback, NOT `res` callback**: When backend returns HTTP 401 (e.g., `return jsonify({...}), 401`), axios routes it to the `err` handler (`err.response.status === 401`), NOT the `res` handler (`res.data.code === 401`). Token refresh logic **MUST** be in the `err` callback, not `res`.
- **Axios interceptor token refresh -- async race condition**: Without `return` on the refresh HTTP call, the logout/redirect code runs synchronously before refresh finishes. Always `return axios.post(...).then(...).catch(...)` so the interceptor awaits the result.\n- **Sticky nav broken by parent `overflow: hidden`**: `position: sticky` is disabled when ANY ancestor has `overflow: hidden`/`clip`, because the parent becomes a scroll container. Fix: remove `overflow: hidden` from parent wrappers (`#app-root`, layout containers). Check both CSS and `<style>` blocks.\n- **CSS `@keyframes` with `var(--x)` — missing intermediate translate**: If a keyframe animation uses `var(--x)` for `translate()` and an intermediate keyframe sets `transform: scale(N)` without `translate(...)`, the scale resets translate to `(0,0)`. Fix: include `translate(calc(var(--x) * <fraction>))` at EVERY keyframe.\n- **Deployment file permission errors**: `cp` preserves source permissions. New files with `600` permissions cause Nginx 403. Always `chmod 644` after copying static assets to web root. Verify with `curl -s -o /dev/null -w \"%{http_code}\" <url>` before declaring done. Add to deploy scripts.
- **tar-extract + blanket `chmod 644` on a directory = Nginx 403 blank page (hit twice in one session, two different servers)**: When deploying a built SPA via `tar xzf` into the web root and then running a blanket `chmod 644` to fix permissions, `644` is also applied to **directories** (e.g. `assets/`), stripping the `x` execute bit. Nginx (running as `www-data`/`nginx`) cannot enter the directory, so every asset returns **403**: `index.html` loads fine, page renders blank with ZERO console errors because JS never loads. Root-cause signature: `stat -c '%a' <dir>` shows `644` on a directory; Nginx error.log shows `open() ".../assets/x.js" failed (13: Permission denied)`. Fix — apply 644 to files and 755 to directories separately, then chown to the web user:
  ```bash
  sudo find /var/www/<app> -type d -exec chmod 755 {} \;
  sudo find /var/www/<app> -type f -exec chmod 644 {} \;
  sudo chown -R www-data:www-data /var/www/<app>
  ```
  Verify Nginx-side readability with `sudo -u www-data ls <webroot>/assets/ | head`, then curl the entry chunks. Note: `du`/`ls` as the login user may still report "Permission denied" for root-owned files after tar-extract even when the web server can read them — always verify as the web user, not the SSH user.
- **Browser caches 403 responses — "still blank" after the fix**: when a page served 403/blank during an outage, the browser caches the failed page+assets. After fixing permissions the site still looks blank until a hard refresh (`Ctrl+Shift+R`) or cache clear. After any 403-fix, tell the user to hard-refresh; verify yourself in a fresh browser session, not the previously-cached one.\n- In an existing application, detouring into UI redesign or broad repo sweeps before patching the current handlers and services.
- **Dual-server Nginx reverse proxy**: When frontend static files and backend API live on different servers, Nginx must proxy both `/api/*` and `/uploads/*` to the backend. Security groups on the backend server should whitelist only the public server's IP. See `references/dual-server-deployment.md`.
- **Nginx `add_header` cache override trap**: `expires 1h` sets `Cache-Control: max-age=3600`, but a sibling `add_header Cache-Control "public"` in the same location OVERWRITES the `max-age` -- result is `Cache-Control: public` with no max-age. Browsers revalidate on every visit. Fix: either remove the `add_header` (let `expires` alone set Cache-Control) or write `add_header Cache-Control "public, max-age=3600"` as a single atomic value. Additionally, a server-level `add_header Cache-Control "no-store"` leaks into ALL child locations -- each location that wants caching must set its own `add_header Cache-Control` to break inheritance (any `add_header` in a child replaces ALL parent `add_header` for that header name). See `references/nginx-cache-header-pitfalls.md`.
- **File upload permission errors**: Always use app-relative paths (e.g., `os.path.join(os.path.dirname(__file__), 'uploads')`), never hardcoded system paths like `/var/www/`. The Flask process user (e.g., `ubuntu`) must own the directory. See `references/upload-permission-errors.md`.
- **Flask upload save directory vs static serve directory mismatch**: When Flask serves `/uploads/<path:filename>` via `app.route` pointing to `app/uploads/`, the upload code must save to the **same** directory. Saving to `backend/uploads/idcards/` (one level up from `app/`) creates files that exist on disk but return HTTP 404 from the Flask route. Fix: use the identical base path in both the upload function and the static route. Pattern: `os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'uploads', 'idcards')` for Flask project structure where `main.py` is in `backend/` and `app/` is a subdirectory.
- **FormData field name mismatch between frontend and backend**: Vue frontend appends to FormData with one key (`form.append('image', file)`) but Flask backend checks a different key (`request.files['file']`). No error message indicates the mismatch — the backend returns `'请选择图片'` because the expected key doesn't exist. Fix: always verify both sides use the same field name, or make the backend accept multiple field names with `request.files.get('file') or request.files['image']`.
- **Vue SFC CSS class mismatch between template and scoped style**: Template HTML uses class names like `pd-icon`, `pd-body`, `pd-agree` but the scoped `<style>` block defines different class names like `privacy-icon`, `privacy-content`, `privacy-check-row`. Result: the component renders in the DOM with no visual styling — completely invisible text, no checkbox border, no button gradient. The Vue compiler does NOT warn about undefined CSS classes. Fix: after writing scoped styles, grep the HTML template for class names and verify each one has a corresponding rule in the style block. Use `grep -o 'class="[^"]*"' | tr ' ' '\n' | sort -u` on the template section and cross-check against the CSS section.
- **SMTP email verification codes**: When using email verification codes with gunicorn, always store codes in the database (not in-memory dicts) because gunicorn workers are separate processes with independent memory. QQ mail requires an SMTP authorization code (not the login password). See `references/email-smtp-verification.md`.

## Engineering constitution (non-negotiable)

These rules override convenience. Treat them as a gate before saying "done".

### 1. TypeScript -- do not silence the type system

- **Do NOT use `any` to bypass type errors.** Not `: any`, not `as any`, not `@ts-ignore`, not `@ts-nocheck`, not `@ts-expect-error` without a written justification. `any` propagates silently and defeats the only compile-time safety net this project has.
- When a type error appears, fix the root cause:
  - Missing / wrong library types -> install `@types/...`, or narrow the import, or write a precise `interface` / `type` for the shape you actually use.
  - Shape is genuinely unknown at the boundary (JSON from an API, `postMessage` payload, `window.*` injection) -> type it as `unknown` and narrow with a type guard (`typeof`, `in`, a discriminator field, or `zod` / equivalent).
  - Third-party type is wrong -> augment via `declare module` in a local `.d.ts`, not `any`.
  - Truly dynamic case (e.g. generic event bus) -> use a generic `<T>` with a constraint, not `any`.
- `unknown` + narrowing is the acceptable escape hatch. `any` is not.
- If you genuinely cannot avoid `any` for a specific line (extremely rare), leave a one-line comment with **why** and **what would remove it**, so reviewers can audit.
- The same spirit applies to ESLint: do not sprinkle `// eslint-disable` to mute the real signal. Fix the rule violation, or discuss before disabling.

### 2. Self-verify before claiming done

Before making any non-trivial code or configuration change, you must first follow the Change Safety Protocol in `cloudbase-platform/references/protocols/change-safety-protocol.md` (declare impact -> user confirmation -> post-edit verification).
Before any static hosting publish or custom domain work, complete the checks in `cloudbase-platform/references/protocols/deployment-gate.md`.

Saying "I've implemented it" / "fixed it" / "it should work" without evidence is not acceptable. Before declaring completion, you must actually run the checks and report the result.

**Static / build layer (always, when applicable):**

- `tsc --noEmit` (or `vue-tsc --noEmit`) passes cleanly -- zero errors, zero suppressed diagnostics you added.
- `eslint` / project linter passes on changed files.
- The project's build command (`npm run build` / `pnpm build` / `vite build`) completes without new warnings that you introduced.
- The project's unit tests pass if they exist and cover the touched area.

**Runtime / browser layer (whenever the change affects rendering, routing, forms, auth, or async flows):**

- Use the **`agent-browser`** tool to actually open the page and reproduce the user-visible flow. Follow `browser-testing.md` for the concrete workflow.
- Confirm: the target route loads, the interaction you claim to have fixed behaves the way you claim, no new console errors are introduced, and no regression in the adjacent routes you touched.
- Record what you checked (route, action, expected result, actual result).

**Only after both layers pass** may you say the task is done. If either layer cannot be executed locally (e.g. blocked by credentials, missing backend, paid API), say so explicitly and list exactly which step is still unverified -- do not gloss over it.

### 3. Do not paper over failures

- Do not wrap broken logic in `try { ... } catch {}` to make the error go away.
- Do not delete or skip a failing test to make CI green -- fix it, or explain why the test is actually wrong and change the test with justification.
- Do not mark a task complete because "the code compiles". Compilation is the bare minimum, not the goal.

## When to use this skill

Use this skill for Web engineering work such as:

- Implementing React or Vue pages and components
- Setting up or maintaining Vite-based frontend projects
- Handling routing, data loading, forms, and build configuration
- Running browser-based validation and smoke checks
- Integrating CloudBase Web SDK and static hosting when the project needs CloudBase capabilities

**Do NOT use for:**
- UI direction or visual system design only; use `ui-design`
- Mini program development; use `miniprogram-development`
- Backend service implementation; use `cloudrun-development` or `cloud-functions`

## How to use this skill (for a coding agent)

1. **Clarify the execution surface**
   - Confirm whether the task is framework setup, page implementation, debugging, deployment, validation, or CloudBase integration.
   - Keep the work scoped to the actual Web app surface instead of spreading into unrelated backend changes.
   - If the workspace is an existing application with TODOs, treat it as a targeted repair task, not a greenfield build.

2. **Follow framework and build conventions**
   - Prefer the existing project stack if one already exists.
   - For new work, treat Vite as the default bundler unless the repo or user constraints say otherwise.
   - Put reusable app code under `src` and build output under `dist` unless the repo already uses a different convention.
   - In an existing application with fixed structure, inspect the files that already own the flow before reading broad docs: `src/lib/backend.*`, `src/lib/auth.*`, `src/lib/*service.*`, route guards, and the page handlers bound to submit buttons.

3. **Validate through the browser, not only by reading code**
   - For interaction, routing, rendering, or regression checks, use `agent-browser` workflows from `browser-testing.md`.
   - Prefer lightweight smoke validation for changed flows before claiming the frontend work is complete.

4. **Treat CloudBase as an integration branch**
   - Use CloudBase Web SDK and static hosting guidance only when the project actually needs CloudBase platform features.
   - Reuse `auth-tool` and `auth-web` for login or provider readiness instead of re-describing those flows here.

## Core workflow

### 1. Choose the right engineering path

- **React / Vue feature work**: implement within the app's existing component, routing, and state conventions
- **New Web app**: prefer Vite unless the repo already standardizes on another toolchain
- **Debugging and regressions**: reproduce in browser, narrow to a specific page or interaction, then patch
- **CloudBase integration**: wire in Web SDK, auth, data, or static hosting only after the base frontend path is clear

### 2. Keep implementation grounded in project reality

- Follow the repo's package manager, scripts, and lint/test patterns
- Avoid framework rewrites unless the user explicitly asks for one
- Prefer the smallest viable page/component/config change that satisfies the task
- In TODO-based apps, complete the existing implementation directly instead of creating parallel helpers, sample pages, or detached prototypes

### 3. Validate changed flows explicitly

- Run the relevant local build / lint / typecheck / test command when available. A clean `tsc --noEmit` and a clean project build are the minimum bar -- not proof of correctness.
- For anything user-visible (routing, forms, rendering, auth, async flows), open the affected page or flow in a browser with **`agent-browser`**. Code reading alone is not sufficient evidence -- see the Engineering constitution above.
- Record what was checked: route, action, expected result, actual result, and any remaining gap.

## CloudBase Web integration

Use this section only when the Web project needs CloudBase platform features.

### Web SDK rules

- Prefer npm installation for React, Vue, Vite, and other bundler-based projects
- Use the CDN only for static HTML pages, quick demos, embedded snippets, or README examples
- Only use documented CloudBase Web SDK APIs; do not invent methods or options
- Keep a shared `app` or `auth` instance instead of re-initializing on every call
- If the user only provides an environment alias, nickname, or other shorthand, resolve it to the canonical full `EnvId` before writing SDK init code, console links, or config files. Do not pass alias-like short forms directly into `cloudbase.init({ env })`.

### Authentication boundary

- Authentication must use CloudBase SDK built-in features
- Do not move Web login logic into cloud functions
- For provider readiness, login method setup, or publishable key issues, route to `auth-tool` and `auth-web`

### Static hosting defaults

- Build before deployment
- Prefer relative asset paths for static hosting compatibility
- Use hash routing by default when the project lacks server-side route rewrites
- If the user does not specify a root path, avoid deploying directly to the site root by default
- **SPA routing (History mode)**: when using React Router / Vue Router in History mode (not hash mode), configure the CloudBase static hosting **"404 error document"** to `index.html`. Otherwise refreshing or directly visiting any sub-route returns `NoSuchKey` / 404 error, because the static hosting looks for a file at that path instead of falling through to `index.html` for the SPA to handle routing.

  Use the MCP tool to apply this:
  ```json
  manageHosting({ action: "setWebsiteDocument", indexDocument: "index.html", errorDocument: "index.html" })
  ```

  Then verify with:
  ```json
  queryHosting({ action: "websiteConfig" })
  ```

### CloudBase quick start

```js
// npm install @cloudbase/js-sdk
import cloudbase from "@cloudbase/js-sdk";

const app = cloudbase.init({
  env: "your-full-env-id", // Canonical full CloudBase environment ID resolved from envQuery or the console
});

const auth = app.auth();
```
