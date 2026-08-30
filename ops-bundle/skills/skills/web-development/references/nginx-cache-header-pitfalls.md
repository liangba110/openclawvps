# Nginx Cache Header Pitfalls

## Problem: `add_header Cache-Control` overrides `expires`

`expires 1h` internally sets `Cache-Control: max-age=3600`. If the same location block also has:

```nginx
location /assets/ {
    expires 1y;
    add_header Cache-Control "public";  # BUG: overrides max-age!
}
```

The result is `Cache-Control: public` (no `max-age`) — browsers revalidate every time.

**Fix:** Remove `add_header` and let `expires` alone control Cache-Control:

```nginx
location /assets/ {
    expires 1y;
    # No add_header Cache-Control — expires handles it
}
```

Or unify both in one value:

```nginx
location /assets/ {
    expires 1y;
    add_header Cache-Control "public, immutable, max-age=31536000";
}
```

## Problem: Server-level `add_header Cache-Control "no-store"` leaks into all locations

```nginx
server {
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;

    location /assets/ {
        expires 1y;                       # sets max-age=31536000
        add_header Cache-Control "public"; # overrides server-level
    }
}
```

Nginx rule: **Any `add_header` in a child block replaces ALL parent `add_header` directives** for that header name. So the location's `add_header Cache-Control "public"` replaces the server's `no-store`. BUT: if you omit `add_header` in the child, the server-level `no-store` propagates down unfiltered.

**Fix:** Every location that needs a specific cache policy must explicitly set its own `add_header Cache-Control` to break inheritance.

## Verification

```bash
curl -sI https://example.com/assets/style.css | grep -i 'cache-control'
```

Expected output for hashed assets:
```
Cache-Control: public, immutable, max-age=31536000
```

For `index.html`:
```
Cache-Control: no-cache, no-store, must-revalidate
```
