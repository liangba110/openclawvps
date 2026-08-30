# Chinese Quote Pitfalls in Python Strings (CRITICAL — Causes SyntaxError → 502)

## Symptom

Backend worker crashes on boot. Nginx returns 502 Bad Gateway for all API endpoints. Page renders blank with no console errors. Browser dev tools shows `GET /api/health 502`.

```
sudo journalctl -u ttdazi --no-pager -n 50 | grep 'SyntaxError'
# SyntaxError: invalid syntax. Perhaps you forgot a comma? (faq.py, line 54)
```

The file looks syntactically OK in your editor. The error only fires at Python parse time.

## Root Cause

Chinese double quotes `"..."` (full-width U+201C / U+201D) are visually almost identical to English ASCII `"` (U+0022). When you paste a Chinese string containing `"` into a Python source file expecting ASCII, Python sees the Chinese quote as a regular character — but **your text editor's auto-replace often converts the next ASCII `"` into Chinese `"` while leaving the rest as ASCII**.

The string ends at the first unescaped ASCII `"` (or Chinese `"`), and Python then parses the next characters as code → SyntaxError on line containing `reply="..."`.

**Example broken code:**
```python
STATIC_FAQ = [
    {"keywords": ["充值"],
     "reply": "📋 详情：选择陪玩师→"立即预约"→选择时长→支付。"},
    #                ↑↑↑↑↑↑↑↑↑↑   ↑↑↑
    #  ASCII " closes the string  ↑↑↑↑↑↑↑↑↑↑↑
    #  Chinese 〃 leaves dangling  Chinese " causes SyntaxError
]
```

## Detection

```bash
# Find Chinese quotes in .py files
python3 -c "
import re
for f in ['/opt/ttdazi/backend/app/faq.py']:
    with open(f) as fp:
        for i, line in enumerate(fp, 1):
            for ch in ['\u201c', '\u201d']:
                if ch in line:
                    print(f'{f}:{i}: {line.rstrip()}')
"
```

Or grep for the Unicode codepoints:
```bash
grep -rn $'\u201c\|\u201d' /opt/ttdazi/backend/app/*.py
```

## Fix Rules

**NEVER use Chinese double quotes `"..."` in Python strings.** Use:

| Replacement | When |
|-------------|------|
| `"..."`  | 引用术语、按钮名、提示 |
| `'...'` | 简短引用 |
| `「...」` | 强调引用（推荐替代双引号） |

**Example corrected:**
```python
STATIC_FAQ = [
    {"keywords": ["充值"],
     "reply": "📋 详情：选择陪玩师→「立即预约」→选择时长→支付。"},
]
```

## Why This Is Hard to Catch

1. **Editor visual confusion:** `"立即预约"` looks the same as `"立即预约"` to the human eye
2. **Linters don't flag it:** Python syntax error only fires at parse time
3. **String concatenation may "work":** If the Chinese quotes happen to land inside an existing string, no error fires (until a colleague edits the surrounding code)
4. **Common copy-paste source:** WeChat messages, QQ messages, web content all use Chinese punctuation

## Prevention

When editing Python source files containing Chinese text:
1. After ANY edit to a `.py` file with Chinese content, run: `python3.12 -c "from app import MODULE_NAME"` to verify it imports
2. Use ASCII single/double quotes in Python source. Wrap Chinese UI text in `「」` brackets
3. Set editor to highlight non-ASCII characters so Chinese quotes stand out
4. In `grep` test for `\u201c|\u201d` before committing

## Diagnosis Flow When 502 Hits Suddenly

```bash
# 1. Check if backend is up
sudo systemctl status ttdazi

# 2. Look for SyntaxError
sudo journalctl -u ttdazi --no-pager -n 30 | grep -i 'syntax\|error' | tail -10

# 3. Verify the module imports
cd /opt/ttdazi/backend && python3.12 -c "from app import MODULE_NAME"

# 4. If SyntaxError, find Chinese quotes
grep -n '[\u201c\u201d]' app/MODULE_NAME.py

# 5. Replace them with ASCII " or 「」
# 6. Restart
sudo systemctl restart ttdazi
```

## Related: Half-Width vs Full-Width Punctuation

Same applies to:
- `'` `'`
- `,` `,`
- `:` `:`
- `(` `（`

When pasting Chinese text into Python files, ALWAYS convert Chinese punctuation to ASCII equivalents in source code.