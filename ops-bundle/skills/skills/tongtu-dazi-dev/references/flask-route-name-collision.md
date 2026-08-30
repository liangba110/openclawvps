# Flask Route Name Collision — Debug Checklist

## Symptom

```
gunicorn.errors.HaltServer: Worker failed to boot
AssertionError: View function mapping is overwriting an existing endpoint function: admin.review_delete
```

Server enters crash loop (auto-restart exits with code 3 every time).

## Root Cause

Flask disallows two route-handling functions with the **same Python function name** inside the same blueprint, even if they have different URL paths and HTTP methods.

```python
# ❌ CRASHES — both functions named 'review_delete'
@admin_bp.route('/reviews/<int:rid>', methods=['DELETE'])
def review_delete(rid):
    ...

@admin_bp.route('/review/delete', methods=['POST'])  
def review_delete():  # ← same name as above!
    ...
```

## Diagnosis

```bash
# After error, grep for duplicate function names in the blueprint
grep -n 'def review_delete\|def review_status\|def complaint_list' backend/app/admin.py | sort
# If same function name appears on multiple lines → collision
```

## Fix

1. **Rename one function** to be unique: `def admin_review_delete()` instead of `def review_delete()`
2. OR **remove the old route** if it's been replaced by the new one
3. OR **consolidate** into a single function that handles both HTTP methods

## Prevention

Before adding any new route to a blueprint:
```bash
grep -n "def FUNCTION_NAME" backend/app/admin.py
```

If the function name already exists, pick a unique name.
