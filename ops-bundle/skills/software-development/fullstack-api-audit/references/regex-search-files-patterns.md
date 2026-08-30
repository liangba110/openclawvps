# Lightweight API Audit via search_files (Tool-Based Alternative)

When Python script execution is unavailable or inconvenient, use Hermes's native `search_files` tool directly.

## Gather Frontend API Calls

```bash
# All api.get/post/put/delete calls with static string paths
search_files(
    pattern="api\\.(get|post|put|delete)\\(",
    file_glob="*.{vue,js}",
    path="/path/to/frontend/src"
)
```

This returns grouped output with file paths, line numbers, and matching lines.

## Gather Backend Routes

```bash
# All @bp.route definitions
search_files(
    pattern="\\.route\\(",
    file_glob="*.py",
    path="/path/to/backend/app"
)
```

## Gather Blueprint Prefixes

```bash
# All Blueprint definitions with url_prefix
search_files(
    pattern="Blueprint\\(",
    file_glob="*.py",
    path="/path/to/backend/app"
)
```

## Cross-Reference Method

1. Walk through each unique frontend path from the search output
2. Resolve it to the full URL by prepending `/api` (frontend baseURL)
3. Match against backend routes by concatenating blueprint `url_prefix` + `route`
4. For dynamic routes (`<int:id>`), normalize to a parameter pattern

## What to Check

| Check | Tool Command |
|-------|-------------|
| Frontend calls without backend | Manual comparison of both search outputs |
| Backend routes never called | Cross-reference: all backend routes minus matched frontend calls |
| Method mismatch | Compare the HTTP method in `api.get()` vs `methods=['POST']` |
| Blueprint registered but unused | Check if any frontend calls match the blueprint prefix |

## Example Output Format

```
## ❌ BROKEN (frontend calls with no backend route)
| File:Line | Method | Path | Note |

## ⚠️ UNUSED (backend routes never called)
| Blueprint | Route | Method | Note |

## ✅ MATCHED
| Path | Method | Status |
```
