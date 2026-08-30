# Flask In-Memory Rate Limiting Middleware

## When to Use

- Simple per-IP rate limiting without external dependencies (Redis)
- Good for low-traffic apps (single server, <100 concurrent users)
- NOT suitable for multi-worker gunicorn (per-process memory means limits reset per worker)

## Pattern: Sliding Window per IP

```python
import time

_rate_limits = {}

def rate_limit(key, max_requests=60, window=60):
    """
    Sliding window rate limiter.
    
    Args:
        key: unique identifier (e.g., 'reg:1.2.3.4')
        max_requests: max allowed in the window
        window: time window in seconds
    
    Returns:
        True if allowed, False if rate limited
    """
    now = time.time()
    if key not in _rate_limits:
        _rate_limits[key] = []
    # Purge expired entries
    _rate_limits[key] = [t for t in _rate_limits[key] if now - t < window]
    if len(_rate_limits[key]) >= max_requests:
        return False
    _rate_limits[key].append(now)
    return True
```

## Usage in Route Handlers

```python
from flask import request

@app.route('/api/auth/register', methods=['POST'])
def register():
    ip = request.remote_addr or 'unknown'
    if not rate_limit(f'reg:{ip}', max_requests=5, window=60):
        return jsonify({'code': 429, 'msg': '操作太频繁，请稍后重试'}), 429
    # ... normal registration logic
```

## Important Notes

1. **Multi-worker inaccuracy**: Each gunicorn worker has its own `_rate_limits` dict. A user hitting 5 requests per minute across 3 workers could make 15 requests before hitting the limit. This is acceptable for rough abuse prevention but NOT for hard rate enforcement. For precise limits, use Redis or Nginx `limit_req`.

2. **Memory leak prevention**: The purge step (`_rate_limits[key] = [t for t in ... if ...]`) ensures expired entries are cleaned up. Old keys with no recent activity will eventually have empty lists, but the dict entry itself lingers. For production, add a periodic cleanup cron or use a TTL-based approach.

3. **Non-blocking**: The in-memory approach is fast (~0.001ms per check) and doesn't add network latency.
