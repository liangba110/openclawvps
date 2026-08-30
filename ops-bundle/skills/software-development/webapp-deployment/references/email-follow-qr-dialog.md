# Follow-Official-Account QR Dialog Before Email Verification Code

## Flow

1. User fills in email address (username + domain dropdown)
2. Clicks "获取验证码"
3. Modal overlay appears with QR code image + "已关注，发送验证码" button + "稍后再说" dismiss
4. User confirms → SMTP verification code sent to email
5. Countdown starts on the "获取验证码" button

## Template pattern

```vue
<div v-if="showQrDialog" class="qr-overlay" @click.self="showQrDialog = false">
  <div class="qr-dialog">
    <div class="qr-dialog-title">📱 关注公众号</div>
    <img src="@/assets/qr-code.jpg" class="qr-dialog-img" alt="公众号二维码" />
    <p class="qr-dialog-tip">请使用微信扫描上方二维码<br />关注公众号后获取验证码</p>
    <button class="btn-primary" @click="confirmFollow">已关注，发送验证码</button>
    <span class="qr-dialog-close" @click="showQrDialog = false">稍后再说</span>
  </div>
</div>
```

## Pitfalls

- **`@click.self` on overlay** — prevents closing when clicking the dialog content itself
- **`@mousedown.prevent` on list items** — prevents blur from hiding the element before click
- **Image must be in `src/assets/`** (Vite processes it) not `public/`
- **QR image change** — replace `src/assets/qr-code.jpg` and rebuild

## Future enhancement

For real QR code verification, integrate WeChat Official Account API:
1. Generate a unique scene ID per email registration
2. Create a temporary QR code via WeChat API
3. Listen for WeChat scan-SUBSCRIBE event webhook
4. Auto-send verification code upon receiving the event
