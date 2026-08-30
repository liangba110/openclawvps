# Platform Review Module — Real-Name Verification + Content Filtering + Reports

## Database Tables

- `verify_application` — real-name ID submissions (status: 0=pending,1=approved,2=rejected)
- `rank_verify` — companion rank screenshot review
- `sensitive_words` — keyword blacklist for content moderation
- `reports` — user complaints (target_type: companion/message/review)

## Backend File

`backend/app/platform_review.py` — Blueprint `platform_review_v2` at `/api/review/v2`

## VerifyIdentity.vue — 3-Step Flow

### Step 1: Privacy Overlay (forced read + agree)

```html
<div v-if="step === 1" class="privacy-overlay">
  <div class="privacy-dialog">
    <h3>实名认证说明</h3>
    <p>根据《网络安全法》第二十四条及《个人信息保护法》要求...</p>
    <div>信息用途: 账号登记·身份核验·交易安全·法律法规存档</div>
    <div>隐私承诺: 加密存储·绝不泄露·仅后4位可见·可申请删除</div>
    <p>点击同意即表示已阅读并同意《隐私政策》及《用户协议》</p>
    <label @click="agreed = !agreed">
      <span class="pd-check" :class="{checked: agreed}">{{ agreed ? '✓' : '' }}</span>
      <span>我已阅读并同意以上说明</span>
    </label>
    <button :disabled="!agreed" @click="step = 2">请先勾选同意</button>
    <p v-if="!agreed" class="pd-tip">↑ 请先勾选上方同意条款</p>
  </div>
</div>
```

**CRITICAL:** The overlay must be OUTSIDE `<div class="verify-page">` but inside `<template>`, otherwise `position: fixed` is scoped to the parent div. Always check with `</div>` closing the page container before the overlay.

### Step 2: ID Card Upload (front + back)

```html
<div class="uc-box" @click="uploadId('front')">
  <img v-if="frontImg" :src="frontImg" class="uc-preview" />
  <div v-else class="uc-placeholder">📸 点击拍照或上传</div>
</div>
```

- Hidden `<input type="file" ref="fileInput">`
- `onFileSelected()`: FormData → `POST /api/review/v2/verify/upload-id`
- On success: `frontImg = r.url`, OCR auto-fills `realName` + `idCard`

### Step 3: Submit

`POST /api/review/v2/verify/submit` with `{real_name, id_card, id_card_front, id_card_back}`

## ID Card Upload Backend (`platform_review.py`)

```python
@review_bp.route('/verify/upload-id', methods=['POST'])
@login_required
def upload_id_card():
    file = request.files['image']
    # Validation chain:
    # 1. Size ≤ 5MB
    # 2. File header: PNG or JPEG magic bytes
    # 3. Dimensions >= 640x480, aspect ratio ≤ 2:1
    # 4. Save to app/uploads/id_cards/
    # 5. OCR attempt (Tencent Cloud IDCardOCR, optional — wraps in try/except)
    #    Validates ID card expiry date
    # 6. Return {url, ocr: {name, id_card, valid_date, valid_forever}}
```

## Sensitive Word Filtering

- 20+ default words loaded on startup
- `check_content(text)` → `(ok, reason)` — used in chat messages and companion intro
- Filters: {色情, 赌博, 诈骗, 微信, QQ, 二维码, 外挂, 手机号 regex, ...}
- Auto-load from `sensitive_words` table, fallback to defaults if empty
- Apply via `from app.platform_review import check_content`

## Report/Complaint System

- `POST /api/review/v2/report` — `{target_type, target_id, reason}`
- Admin: `GET /api/review/v2/reports` — list with reporter name
- Admin: `POST /api/review/v2/report/handle` — `{id, status}`

## Admin Review Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/review/v2/verify/list` | GET | Pending verification applications |
| `/api/review/v2/verify/approve` | POST | Approve → sets user.verify_status=1 |
| `/api/review/v2/verify/reject` | POST | Reject with reason |
| `/api/review/v2/reports` | GET | Report list |
| `/api/review/v2/report/handle` | POST | Handle report |

## Pitfalls

1. **Blueprint name conflict**: Flask disallows two blueprints with same internal name. `app/review.py` (rating reviews) uses name `'review'` at `/api/review`. `app/platform_review.py` must use a DIFFERENT name: `Blueprint('platform_review_v2', ...)` and a DIFFERENT prefix: `/api/review/v2`.
2. **Import duplication**: When importing two blueprints into `main.py`, the second `from app.platform_review import review_bp` overwrites the first `from app.review import review_bp`. Must use `as` alias: `from app.review import review_bp as old_review_bp` / `from app.platform_review import review_bp as platform_review_bp`.
3. **OCR try/except**: Always wrap TencentCloud SDK imports in try/except — not installed by default. Without SDK, OCR returns empty fields and user enters manually.
4. **Image validation**: PNG header `\x89PNG\r\n\x1a\n`, JPEG header `\xff\xd8\xff\xe0`. File extension can be spoofed; header bytes cannot.
