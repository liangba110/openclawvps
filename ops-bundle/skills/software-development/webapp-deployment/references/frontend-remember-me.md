# Frontend: Remember Me (记住账号密码)

A pattern for saving and auto-filling login credentials via `localStorage`.

## Implementation (Vue 3)

### Template — add checkbox below password field

```html
<div class="remember-row">
  <label class="remember-label">
    <input type="checkbox" v-model="remember" />
    <span>记住账号密码</span>
  </label>
</div>
```

### Script — load saved data on mount, save after login

```js
import { ref } from 'vue'

const phone = ref('')
const password = ref('')
const remember = ref(false)

// Load saved credentials on page load
const saved = localStorage.getItem('remembered_login')
if (saved) {
  try {
    const data = JSON.parse(saved)
    phone.value = data.phone || ''
    password.value = data.password || ''
    remember.value = true
  } catch (e) {}
}

async function doLogin() {
  // ... login logic ...

  // After successful login, save or clear based on checkbox
  if (remember.value) {
    localStorage.setItem('remembered_login', JSON.stringify({
      phone: phone.value,
      password: password.value
    }))
  } else {
    localStorage.removeItem('remembered_login')
  }
}
```

### Style

```css
.remember-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4px 0 12px;
}

.remember-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #888;
  cursor: pointer;
}

.remember-label input[type="checkbox"] {
  accent-color: #667eea;
  width: 16px;
  height: 16px;
}
```

## Notes

- Uses `localStorage`, so data persists across browser sessions.
- The checkbox defaults to unchecked — user must opt in.
- When unchecked after login, clears saved data.
- For React, same pattern applies with `useState` and `useEffect`.
- **Security consideration**: Passwords in `localStorage` are accessible to any
  JavaScript on the same origin. For higher security apps, consider a session-only
  approach or encrypted storage.
