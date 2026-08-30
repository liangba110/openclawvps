# 2026-07-09 Session Learnings — Financial Audit & Withdrawal System

## Key Fixes

### 1. order.py log_money Import Missing
- `order.py` called `log_money()` but never imported it → silent failure
- Fix: Added `from app.money_log import log_money` to order.py

### 2. admin.py Withdrawal Audit Variable Scope
- `withdrawal_audit()` called `log_money(..., amount, ..., w['amount'])` 
- `amount` was undefined, `w` was defined inside `if cur.rowcount:` block
- Fix: Safe extraction `wd_amount = float(w['amount']) if w and w.get('amount') else 0`

### 3. Payment Route Confusion
- Frontend calls `api.post('/order/pay')` → goes to `order.py`'s `pay()`
- NOT `payment.py`'s `pay()` (which was never called)
- All financial logging must be added to `order.py`'s `pay()`, not `payment.py`'s

### 4. Money Logging Coverage
All files that call `log_money()` must have `from app.money_log import log_money`:
- order.py ✅ (FIXED)
- playmate_api.py ✅
- admin.py ✅
- payment.py ✅
- companion.py ❌ (not needed — no money operations)

## Withdrawal System Changes
- Fee storage: `amount` stores gross (requested amount), `fee` stores fee separately
- Fee deducted from balance via gross amount, net = displayed to user
- Withdrawal fee rate read from site_config `withdraw_fee_rate`
- Platform commission read from site_config `commission_rate`
- Min withdrawal read from site_config `withdraw_min`

## Test Methodology
1. Always check journalctl for real errors (not just `code=1` responses)
2. Backtick character in MySQL queries breaks bash inline Python → use heredoc or temp file
3. After modifying imports, always `find ... -name __pycache__ -exec rm -rf {} +` before restart
