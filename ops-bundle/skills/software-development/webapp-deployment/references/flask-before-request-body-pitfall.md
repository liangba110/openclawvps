# Flask `before_request` JSON Body Consumption Pitfall

## The Problem

Setting `request.json` or `request.get_json()` inside a `@app.before_request` handler triggers Flask's JSON body parsing, which **consumes the request stream**. Even though Flask caches the parsed JSON and route handlers can still read it, the `before_request` handler fires on **every request type** (GET, POST, PUT, etc.). Non-JSON requests (e.g., GET without Content-Type) raise a 415 error that the handler must catch.

**Symptoms of the bug:**
- Clicking buttons does nothing
- No browser console errors
- Backend logs show no requests arriving
- All POST endpoints silently fail

## Why It Happens

```python
# This looks innocent but breaks all POST endpoints:
@app.before_request
def before_request():
    if request.json:  # ← triggers JSON parsing on every request
        request.json_data = sanitize(request.json)
```

The `request.json` property calls Flask's `get_json()` internally. For GET requests without `Content-Type: application/json`, this raises a 415 `Unsupported Media Type` exception. Even wrapping it in try/except leaves `request.json_data` unset for routes that expect it.

## The Fix

**Never access the request body in `before_request`.** Keep `before_request` for:
- Setting response headers (move to `after_request` instead)
- Rate-limiting counters (IP-based, no body access)
- Logging request metadata

**For input sanitization, use one of:**

1. **Inline in route handlers** (simplest):
   ```python
   @app.route('/api/register', methods=['POST'])
   def register():
       data = request.get_json() or {}
       data = sanitize_dict(data)  # sanitize per-route
       ...
   ```

2. **Decorator pattern** (clean for multiple routes):
   ```python
   def sanitize_input(f):
       @wraps(f)
       def decorated(*args, **kwargs):
           if request.method in ('POST', 'PUT'):
               # Read JSON, sanitize, store for route handler
               json_data = request.get_json(silent=True) or {}
               request.sanitized_data = sanitize_dict(json_data)
           return f(*args, **kwargs)
       return decorated

   @app.route('/api/register', methods=['POST'])
   @sanitize_input
   def register():
       data = request.sanitized_data  # already sanitized
       ...
   ```

3. **Security headers belong in `after_request`** (never `before_request`):
   ```python
   @app.after_request
   def add_security_headers(response):
       response.headers['X-Content-Type-Options'] = 'nosniff'
       response.headers['X-Frame-Options'] = 'SAMEORIGIN'
       response.headers['X-XSS-Protection'] = '1; mode=block'
       response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
       return response
   ```

## Verification

After fixing, test every POST endpoint:
```bash
curl -s -X POST http://localhost:5003/api/some-endpoint \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"key":"value"}' | head -c 200
```

Also verify GET endpoints still work:
```bash
curl -s http://localhost:5003/api/health
```
