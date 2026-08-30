# Funds Security — payment_secure.py

Complete reusable pattern for protecting payment-related endpoints.

## Why it matters

Frontend prices/amounts are user-controllable via DevTools, mitmproxy, or replay attacks. Without server-side validation, attackers can:
- Register orders at ¥0.01 (modify `amount` in request)
- Replay payment requests to charge multiple times
- Bypass coupons/discounts by lying about price

## Three-layer defense

### Layer 1: DB Price Trust (ignore client amounts)

```python
# backend/app/payment_secure.py
def get_db_price(companion_id, service_type):
    """从数据库获取陪玩师真实价格，前端传价不可信"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cg.game_id, cg.price_1h, cg.price_2h, cg.price_night
                FROM companion c
                JOIN companion_game cg ON cg.companion_id=c.id
                WHERE c.id=%s AND c.is_online=1
                LIMIT 1
            """, (companion_id,))
            game = cur.fetchone()
            if not game:
                return None, '陪玩师不存在或已下架'
            price_map = {1: float(game['price_1h']), 2: float(game['price_2h']), 3: float(game['price_night'])}
            price = price_map.get(service_type, 0)
            if price <= 0:
                return None, '价格无效'
            return {'game_id': game['game_id'], 'price': price}, ''
    finally:
        conn.close()
```

Use in endpoint:
```python
db_price, err = get_db_price(companion_id, service_type)
if err:
    return fail(err)

amount = db_price['price']  # NEVER trust client's amount field
```

### Layer 2: Idempotent Lock (prevent duplicate charges)

```python
import threading, time

_lock = threading.Lock()
_locks = {}  # {idempotent_key: expire_time}

def idempotent(key_prefix='tx'):
    """装饰器：幂等性保护，防重复提交"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kw):
            data = request.get_json() or {}
            idem_key = data.get('idempotent_key') or f"{key_prefix}_{user_id}_{int(time.time()/10)}"
            with _lock:
                now = time.time()
                # 清理过期锁
                for k in list(_locks.keys()):
                    if _locks[k] < now:
                        del _locks[k]
                if idem_key in _locks:
                    return jsonify({'code': 409, 'msg': '请求处理中，请勿重复提交'}), 409
                _locks[idem_key] = now + 30  # 30秒锁
            try:
                return f(*args, **kw)
            finally:
                with _lock:
                    _locks.pop(idem_key, None)
        return wrapper
    return decorator
```

Frontend generates unique key:
```js
const payload = {
  companion_id: 1,
  game_id: 1,
  service_type: 1,
  idempotent_key: 'order_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
}
```

⚠️ **In-memory locks DON'T survive multi-worker gunicorn restart.** For multi-worker production, migrate to Redis SET NX EX.

### Layer 3: HMAC Sign Module (endpoint tamper detection)

```python
import hashlib

PAYMENT_SECRET = 'ttdazi_payment_2026_secure'

def sign_payload(data: dict) -> str:
    s = '&'.join(f'{k}={v}' for k, v in sorted(data.items()) if k != 'sign')
    return hashlib.md5((s + PAYMENT_SECRET).encode()).hexdigest()

def verify_sign(data: dict) -> bool:
    sign = data.get('sign', '')
    return sign and sign == sign_payload({k: v for k, v in data.items() if k != 'sign'})

def require_sign(f):
    @wraps(f)
    def wrapper(*args, **kw):
        data = request.get_json() or {}
        if not verify_sign(data):
            return jsonify({'code': 403, 'msg': '请求签名无效', 'data': None}), 403
        return f(*args, **kw)
    return wrapper
```

Apply to recharge/withdraw endpoints:
```python
@recharge_bp.route('/create', methods=['POST'])
@require_sign
@idempotent('recharge')
def create_recharge():
    # process recharge
    ...
```

Frontend signs every payment request:
```js
import md5 from 'crypto-js/md5'
const SECRET = 'ttdazi_payment_2026_secure'

function signRequest(payload) {
  const sorted = Object.keys(payload).sort().map(k => `${k}=${payload[k]}`).join('&')
  return md5(sorted + SECRET).toString()
}

const payload = { amount: 100, user_id: 1, timestamp: Date.now() }
payload.sign = signRequest(payload)
api.post('/recharge/create', payload)
```

⚠️ **Secret exposure:** Frontend SECRET can be extracted. For real production, sign server-side via a `/sign-token` endpoint that returns short-lived (60s) signed tokens.

## CRITICAL pitfall — Column name mismatch

When JOINing `companion_game` with `companion` table:

```python
# ❌ FAILS — 'g.id' doesn't exist in `companion_game` table
cur.execute("""
    SELECT g.id as game_id, cg.price_1h ...
    FROM companion c JOIN companion_game cg ON cg.companion_id=c.id AND cg.game_id=c.game_id
    JOIN game g ON g.id=cg.game_id
""")
# → 500: Unknown column 'g.id' in 'field list'

# ✅ CORRECT — read game_id directly from companion_game (no JOIN to game table)
cur.execute("""
    SELECT cg.game_id, cg.price_1h, cg.price_2h, cg.price_night
    FROM companion c JOIN companion_game cg ON cg.companion_id=c.id
    WHERE c.id=%s AND c.is_online=1 LIMIT 1
""")
```

## Status Field Mapping (companion.status int → audit_status string)

The `companion` table uses `status TINYINT(0/1/2)` but frontend expects strings `pending/approved/rejected`:

```python
status_map = {0: 'pending', 1: 'approved', 2: 'rejected'}
info['audit_status'] = status_map.get(info.get('status', 0), 'pending')
```

Required in EVERY endpoint that exposes companion audit status to admin UI (admin list, detail, audit page).

## Verification Suite

```bash
# 1. Backend health
curl -s http://127.0.0.1:5002/api/health

# 2. Idempotency: rapid-fire 3 identical requests, 4th should 409
for i in 1 2 3 4; do
  curl -X POST http://127.0.0.1:5002/api/order/create \
    -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    -d '{"companion_id":1,"game_id":1,"service_type":1,"idempotent_key":"dup_test"}' | head -1
done

# 3. Price tampering: try to register with ¥1 (should use DB price, not ¥1)
curl -X POST http://127.0.0.1:5002/api/order/create \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"companion_id":1,"game_id":1,"service_type":1,"amount":1,"idempotent_key":"price_test"}'
# Verify order.amount in DB is the actual price, not 1
```