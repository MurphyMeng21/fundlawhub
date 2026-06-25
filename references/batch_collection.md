# Batch Collection Strategy (200-300 Files)

This guide covers efficiently collecting 200-300 regulations on a specific topic using the backend APIs.

## Recommended Approach

Use the **Search API** to collect IDs, then the **Download API** to fetch files. Browser automation is only needed as a fallback for edge cases.

## Phase 1: Collect All Target Law IDs (Search API)

```python
import requests
import urllib3
import json
import os
import re

urllib3.disable_warnings()

BASE_URL = "https://flk.npc.gov.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://flk.npc.gov.cn/search",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}


def search_laws(keyword, category_codes=None, authority_codes=None, page=1, size=100, search_type=2):
    """Search laws and return (total, rows).

    search_type: 1=exact title match, 2=fuzzy match.
    Use exact (1) when the target regulation name is known, to reduce noise.
    Use fuzzy (2) for broad topic discovery.
    """
    payload = {
        "searchRange": 1,        # 1=title, 2=content
        "searchType": search_type,
        "searchContent": keyword,
        "pageNum": page,
        "pageSize": size,
        "orderByParam": {"order": "-1", "sort": ""},
        "flfgCodeId": category_codes or [],
        "zdjgCodeId": authority_codes or [],
        "sxx": [], "gbrq": [], "sxrq": [], "gbrqYear": [],
        "xgzlSearch": False,
    }
    resp = requests.post(f"{BASE_URL}/law-search/search/list", headers=HEADERS, json=payload, verify=False, timeout=30)
    data = resp.json()
    return data.get("total", 0), data.get("rows", [])


def collect_ids(keyword, category_codes=None, search_type=2, title_filter=None):
    """Collect all bbbs IDs across pages.

    title_filter: optional substring that must appear in the cleaned title
    (e.g. '物业管理' to drop '轨道交通管理条例' that matched fuzzy content).
    """
    all_ids = []
    page = 1
    while True:
        total, rows = search_laws(keyword, category_codes=category_codes, page=page, size=100, search_type=search_type)
        for row in rows:
            title = re.sub(r"<[^>]+>", "", row.get("title", ""))
            if title_filter and title_filter not in title:
                continue
            all_ids.append({
                "bbbs": row["bbbs"],
                "title": title,
                "category": row.get("flxz"),
                "authority": row.get("zdjgName"),
                "publish_date": row.get("gbrq"),
                "effective_date": row.get("sxrq"),
            })
        if len(all_ids) >= total or not rows:
            break
        page += 1
    return all_ids


# Example 1: known regulation name -> use exact title search
items = collect_ids("物业管理条例", search_type=1)

# Example 2: broad topic -> fuzzy search, then filter titles
items = collect_ids("物业管理", search_type=2, title_filter="物业管理")
print(f"Collected {len(items)} items")

# Save ID list
os.makedirs("collected_regulations", exist_ok=True)
with open("collected_regulations/ids.json", "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=2)
```

### Filter Codes

Fetch valid codes from `GET /law-search/search/enumData`:

- `flfgfl` tree → `flfgCodeId` values (use **leaf** codes, e.g., `230` 地方性法规, not `221` 地方法规)
- `zdjgfl` tree → `zdjgCodeId` values (use leaf codes, e.g., `350` 广东/珠海)

For region classification, prefer `zdjgCodeId` filters when possible. If you must classify from `zdjgName` strings, use the bundled `region_classifier.py`:

```python
from scripts.region_classifier import classify_search_results, build_existence_matrix, save_existence_matrix

# Add province/city/level columns to collected items
classified = classify_search_results(items)

# Generate 32-province existence matrix
matrix = build_existence_matrix(classified)
save_existence_matrix(matrix, "existence_matrix.csv")
```

This handles irregular naming such as "宁夏回族自治区人大常务委员会" and city-level authorities that don't include the province name (e.g. "广州市人民代表大会常务委员会" → 广东省).

## Phase 2: Batch Download (Download API)

```python
import requests
import urllib3
import json
import os
import re
import time

urllib3.disable_warnings()

BASE_URL = "https://flk.npc.gov.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://flk.npc.gov.cn/",
    "Accept": "application/json, text/plain, */*",
}


def get_download_url(bbbs_id, fmt="docx"):
    """Get signed OSS URL for a law."""
    resp = requests.get(
        f"{BASE_URL}/law-search/download/pc",
        params={"format": fmt, "bbbs": bbbs_id},
        headers={**HEADERS, "Referer": f"{BASE_URL}/detail?id={bbbs_id}"},
        verify=False, timeout=15
    )
    data = resp.json()
    if data.get("code") == 200:
        return data.get("data", {}).get("url")
    return None


def download_file(url, output_path):
    resp = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, verify=False, timeout=60)
    if resp.status_code == 200 and "text/html" not in resp.headers.get("Content-Type", ""):
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return True
    return False


output_dir = "collected_regulations"
os.makedirs(output_dir, exist_ok=True)

with open(os.path.join(output_dir, "ids.json"), encoding="utf-8") as f:
    items = json.load(f)

results = []
for i, item in enumerate(items):
    bbbs_id = item["bbbs"]
    title = re.sub(r"[\\/:*?\"<>|]", "_", item["title"])[:50]
    output_path = os.path.join(output_dir, f"{title}.doc")

    url = get_download_url(bbbs_id, "docx")
    if url and download_file(url, output_path):
        results.append({**item, "status": "success", "path": output_path})
        print(f"[{i+1}/{len(items)}] OK: {item['title']}")
    else:
        results.append({**item, "status": "failed", "reason": "download_error"})
        print(f"[{i+1}/{len(items)}] FAIL: {item['title']}")
    time.sleep(0.5)

with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

success = [r for r in results if r["status"] == "success"]
print(f"\nDone: {len(success)}/{len(items)}")
```

## Phase 3: Verification

```python
import os
import json

output_dir = "collected_regulations"
with open(os.path.join(output_dir, "manifest.json"), encoding="utf-8") as f:
    results = json.load(f)

success = [r for r in results if r["status"] == "success"]
failed = [r for r in results if r["status"] == "failed"]

print(f"Total: {len(results)}")
print(f"Success: {len(success)} ({len(success)/len(results)*100:.1f}%)")
print(f"Failed: {len(failed)}")

for r in success:
    path = r["path"]
    if os.path.exists(path):
        size = os.path.getsize(path)
        if size < 1000:
            print(f"WARNING: {path} is suspiciously small ({size} bytes)")
    else:
        print(f"MISSING: {path}")

if failed:
    print("\nFailed IDs for retry:")
    for r in failed:
        print(f"  {r['bbbs']}: {r.get('reason', 'unknown')}")
```

## Expected Timeline

| Phase | Duration | Notes |
|-------|----------|-------|
| ID Collection (API, 100/page) | 1-2 min | ~3 pages × 30s |
| Batch Download (200 files) | 3-5 min | API calls: ~1s per file |
| Verification | 1 min | Script checks |
| **Total** | **~5-8 min** | For 200-300 files |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Search API returns 500 | Check payload field names; capture a fresh request from the browser |
| Download API returns 200 with empty `data` | The format (usually PDF) is unavailable; try `docx` |
| Signed OSS URL returns 403 | The signature expired; re-request a fresh download URL |
| Rate limiting | Increase `time.sleep()` between requests |
| Some laws consistently fail | Use browser automation for those specific items |

## Browser Fallback

If the APIs change or a specific law fails:

1. Use `kimi-webbridge` or Chrome plugin
2. Visit `https://flk.npc.gov.cn/detail?id={bbbs}`
3. Click **下载** → **点击下载**
4. Capture the real request in Network tab and update this doc
