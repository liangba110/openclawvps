# Verification Code Registration Flow

## Overview

A registration flow where users get a verification code from a WeChat Official Account
(公众号) rather than via SMS. The code is generated server-side and "sent" through the
official account's message channel.

## Flow Steps

```
Step 1: User scans WeChat Official Account QR code → follows the account
Step 2: User opens registration page, enters phone number
Step 3: User sends "注册 <phone>" to the official account in WeChat
Step 4: Backend generates 6-digit code → Official account replies with it
Step 5: User enters the code on the registration page
Step 6: Backend verifies code → user sets password → account created
```

## Backend API Endpoints

Three endpoints under `/api/user/`:

### 1. `POST /send-code`
- Input: `{"phone": "13800138000"}`
- Generates 6-digit random code
- Stores in `verify_codes` MySQL table with `phone`, `code`, `verified`, `created_at`
- Returns `{"_dev_code": "123456"}` in dev mode (remove in production)
- Rate-limited: 60-second cooldown per phone

### 2. `POST /verify-code`
- Input: `{"phone": "13800138000", "code": "123456"}`
- Validates code against DB record
- Marks `verified=1` on success
- Expires after 5 minutes

### 3. `POST /register-by-code`
- Input: `{"phone": "13800138000", "code": "123456", "password": "...", "nickname": "..."}`
- Re-validates code (must match AND be marked verified)
- Creates user with role='user'
- Returns JWT token (auto-login on registration)

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS verify_codes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  phone VARCHAR(11) NOT NULL,
  code VARCHAR(6) NOT NULL,
  verified TINYINT DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## Testing in Development

The `send-code` endpoint returns `_dev_code` in the response so developers can test
without a real WeChat integration. The frontend shows this in a yellow hint box.

### Remove before production:
1. Delete `_dev_code` from the `send-code` response
2. Remove the dev-hint div from the Vue template
3. Connect the real WeChat Official Account message webhook

## Pitfalls

- **Gunicorn multi-worker**: Never store verification codes in Python in-memory
  (`_verify_codes = {}`). Gunicorn workers are separate processes and do NOT share
  memory. A `send-code` handled by worker 1 is invisible to `verify-code` on worker 2.
  Always use a shared data store (MySQL, Redis).
- **Code expiration cleanup**: Delete expired codes on read (when user submits a code
  that's older than 5 minutes). Don't rely on periodic cleanup jobs for correctness.
- **Rate limiting cooldown**: Check cooldown before generating a new code, not after.
  Store the `created_at` timestamp and compute elapsed time in the query.
- **Replay protection**: After successful registration, DELETE the verification code
  record so it can't be reused.
