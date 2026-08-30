# Session 6 (2026-07-08 → 07-09) Key Learnings

## get_site_config() pattern

Added to `app/utils.py` — central function for reading `site_config` table values.
Used by: `companion.py` (min_withdraw), `playmate_api.py` (withdraw_fee_rate, min_withdraw), `payment.py` (commission_rate).

## Withdrawal fee implementation

- withdraw table: `amount` (gross), `fee` (decimal), `alipay_account`, `account_name`
- Fee = withdraw_fee_rate% from site_config (default 3%)
- withdrawable = total_income - done - frozen (approved only, not pending/rejected)
- Frozen = pending withdrawals (status=0)
- Rejected withdrawals do NOT count toward withdrawn (status=2 excluded)

## Withdraw status code mapping

Fixed: {0:'审核中',1:'已通过',2:'已拒绝',3:'已到账'} — was {0:'审核中',1:'已通过',2:'已到账',3:'已拒绝'}

## Admin withdrawal audit

`POST /admin/withdrawals/{id}/audit` body: `{status: 1}` (approve) or `{status: 2}` (reject)

## Admin withdrawal list filtering

`GET /admin/withdrawals?status=0` — backend now supports ?status= parameter.

## sibling subagent file conflicts

When using delegate_task, sibling subagents can modify the same files. Always verify imports after parallel edits. Clear `__pycache__/` after changes.

## Vite build failure detection

Always check for `✓ built in Xs` in build output, not just `tail -3`. If a module has a syntax error (e.g. `await` outside async, CSS mismatch), Vite fails to build but previous dist remains.

## Commission calculation consolidation

- `companion.py my_income()` uses `companion_income` field with `(settled=1 OR settle_at <= NOW())`
- `playmate_api.py withdraw()` must use SAME calculation (was using `amount*0.9` with `status>=3`)

## Withdraw fee stored correctly

Store `amount` as the requested gross amount (e.g. 100), not net after fee (e.g. 95). Fee is a separate column.

## Frontend API endpoint mismatch

`/playmate/profile` does NOT exist on backend (blueprint prefix is `/companion/`). Use `/companion/my` for GET, `/companion/profile` for PUT.
