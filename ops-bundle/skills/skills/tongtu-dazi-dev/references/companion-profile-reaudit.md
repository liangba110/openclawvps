# Companion Profile Edit → Re-audit Flow

## Flow

```
Companion edits profile (PlaymateProfile.vue) → clicks "保存修改"
  → PUT /companion/profile (backend update_profile)
    → UPDATE companion SET status=0 (pending review) WHEN games are updated
    → Returns success
  → Frontend shows toast "资料已提交审核"
  → router.push('/companion/register')
    → CompanionRegister onMounted checks:
      → prof.status === 0 → toast "您的资料正在审核中" → router.replace('/playmate/')
```

## Backend: companion.py update_profile()

```python
if games:
    # 设置状态为待审核
    cur.execute("UPDATE companion SET status=0 WHERE id=%s", (cid,))
    # 删除旧记录
    cur.execute("DELETE FROM companion_game WHERE companion_id=%s", (cid,))
    # ... insert new games
```

## Frontend: CompanionRegister.vue onMounted

```javascript
if (prof && prof.id) {
    if (prof.status === 1 || prof.status === 'approved' || prof.status === '已通过') {
        safeToast('您已通过陪玩师审核，无需重复申请')
        router.replace('/')
        return
    }
    if (prof.status === 0 || prof.status === 'pending' || prof.status === '待审核') {
        safeToast('您的资料正在审核中，请耐心等待')
        router.replace('/playmate/')
        return
    }
}
```

## Important

- Only sets status to 0 when `games` (price/play info) is changed
- Does NOT set status to 0 for just nickname/avatar/bio changes (no games data in request)
- After re-audit, admin approves via admin panel: `playmate_audit()` sets status=1
- User is redirected back to PlaymateHome when pending, NOT shown the registration form
