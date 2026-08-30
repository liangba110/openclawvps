# JPEG File Header Detection — Platform Review Upload

**Problem:** `platform_review.py` `upload_id_card()` checked only 3 specific JPEG markers:
```python
# OLD — rejects many valid JPEGs
img_data[:8] not in (b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1')
```

Many cameras/phones produce JPEG with different APP markers (e.g. `\xff\xd8\xff\xdb`, `\xff\xd8\xff\xc0`, `\xff\xd8\xff\xc2`). These were rejected as "请上传JPG或PNG格式图片".

## Fix

Check only the first 2 bytes for JPEG (`\xff\xd8`), let PIL handle deeper validation:

```python
if img_data[:8] == b'\x89PNG\r\n\x1a\n':
    pass  # PNG
elif img_data[:2] == b'\xff\xd8':
    pass  # JPEG (any variant — \xff\xe0, \xff\xdb, \xff\xc0, etc.)
else:
    return fail('请上传JPG或PNG格式图片')
```

PNG check still uses the full 8-byte header (stable). PIL still validates the image can actually be opened.

## Other Validation

- Size: `len(img_data) > 5 * 1024 * 1024` → "图片不能超过5MB"
- Resolution: `w < 640 or h < 480` → "图片分辨率过低"
- Aspect ratio: `w / h > 2.0 or h / w > 2.0` → "图片比例异常"
