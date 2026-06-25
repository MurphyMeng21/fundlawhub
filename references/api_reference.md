# API Reference

## Browser Navigation (Page URLs)

```
https://flk.npc.gov.cn/index                          # Home page
https://flk.npc.gov.cn/search                         # Search results
https://flk.npc.gov.cn/advanceSearch                  # Advanced search
https://flk.npc.gov.cn/detail?id={bbbs}               # Law detail page
https://flk.npc.gov.cn/detail2.html?id={bbbs}         # Alternative detail
```

## Backend API Endpoints

All endpoints below were discovered from the JS bundle. Base URL: `https://flk.npc.gov.cn`

### Detail Info (Working)

```
GET /law-search/search/flfgDetails?bbbs={bbbs_id}
```

Response:
```json
{
  "code": 200,
  "data": {
    "bbbs": "...",
    "title": "法规标题",
    "flxz": "法律",
    "zdjgName": "全国人民代表大会常务委员会",
    "gbrq": "2012-06-30",
    "sxrq": "2013-07-01",
    "sxx": 3,
    "ossFile": {
      "ossWordPath": "prod/20120630/uuid.docx",
      "ossPdfPath": "prod/20120630/uuid.pdf",
      "ossWordOfdPath": "prod/20120630/uuid.ofd",
      "ossPdfOfdPath": "prod/20120630/uuid.ofd"
    },
    "content": { "children": [...] }
  }
}
```

Status codes in `sxx` field: 1=?, 3=有效, possibly others for 已废止/已修改/尚未生效.

### Enum Data (Working)

```
GET /law-search/search/enumData
```

Returns all dropdown values: categories, issuing authorities, etc.

### Home Aggregate (Working)

```
GET /law-search/index/aggregateData
```

Returns category counts and featured/new laws.

### Search List (Working)

```
POST /law-search/search/list
```

**Working payload** (captured from browser, 2026-06):

```json
{
  "searchRange": 1,
  "sxrq": [],
  "gbrq": [],
  "sxx": [],
  "searchType": 2,
  "xgzlSearch": false,
  "searchContent": "出租车",
  "orderByParam": {"order": "-1", "sort": ""},
  "flfgCodeId": [],
  "zdjgCodeId": [],
  "gbrqYear": [],
  "pageNum": 1,
  "pageSize": 20
}
```

| Field | Meaning |
|-------|---------|
| `searchRange` | `1`=标题, `2`=正文 |
| `searchType` | `1`=精确, `2`=模糊 |
| `searchContent` | Search keyword |
| `pageNum` / `pageSize` | Pagination (pageSize up to at least 100) |
| `orderByParam.order` | `"-1"` works; ascending values return 500 |
| `orderByParam.sort` | `""`=默认, `"gbrq"`=公布日期, `"sxrq"`=施行日期, `"sxx"`=时效性, `"flxz"`=分类, `"zdjg"`=机关 |
| `flfgCodeId` | Category filter codes (leaf nodes from `enumData`) |
| `zdjgCodeId` | Issuing authority filter codes (leaf nodes) |
| `sxx` | Status filter codes |
| `gbrq` / `sxrq` | Date range filters `[start, end]` |
| `gbrqYear` | Publish year groups |

Response:
```json
{
  "code": 200,
  "msg": "查询成功",
  "total": 118,
  "rows": [ { "bbbs": "...", "title": "...", ... } ],
  "searchType": 2,
  "searchContent": null
}
```

### Hit Display

```
POST /law-search/search/hitDisplay
```

Body: `{"id": "bbbs_id"}` — returns highlighted search matches.

### Related Materials

```
POST /law-search/search/xgzl
```

Body: `{"id": "bbbs_id", "page": 1, "size": 10}` — related documents.

### Download (Working)

```
GET /law-search/download/pc?format={docx|pdf}&bbbs={bbbs_id}
```

Returns a signed OSS URL for the requested format.

Example response for `format=docx`:
```json
{
  "code": 200,
  "msg": "操作成功",
  "data": {
    "url": "https://flkoss.obs-bj2.cucloud.cn/prod/.../uuid.doc?X-Amz-Signature=...",
    "urlIn": "http://172.16.220.27:38080/law-search/file/download?..."
  }
}
```

Use `data.url` (signed OSS URL) to download the actual file. The `urlIn` is an internal endpoint and not reachable externally.

**Note:** `format=pdf` may return code 200 with empty `data` for laws that do not have a PDF version. Fall back to `docx` in that case.

### Batch Download

```
POST /law-search/download/batch
```

Body: `{"ids": ["id1", "id2"]}` — batch download.

### Search Prompts

```
GET /law-search/prompts/search?title={keyword}
```

Returns search suggestions.

## File Download

### Recommended: Download API

The official download API is the most reliable way to get files. Do not use the `ossFile` URLs from the detail API directly — they often return the SPA index page.

```bash
# Download a law as DOCX
python scripts/download.py --download <bbbs_id> --format docx output.doc

# Download as PDF (when available)
python scripts/download.py --download <bbbs_id> --format pdf output.pdf
```

Or in Python:

```python
import requests, urllib3
urllib3.disable_warnings()

base = "https://flk.npc.gov.cn"
bbbs = "ff80808172b5f24f0172d9f04f0910af"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{base}/detail?id={bbbs}",
}

# 1. Get signed URL
resp = requests.get(f"{base}/law-search/download/pc?format=docx&bbbs={bbbs}", headers=headers, verify=False)
url = resp.json()["data"]["url"]

# 2. Download file
file_resp = requests.get(url, headers={"User-Agent": headers["User-Agent"]}, verify=False)
open("output.doc", "wb").write(file_resp.content)
```

### Detail API `ossFile` URLs (Unreliable)

The detail API response includes:

```json
{
  "ossFile": {
    "ossWordPath": "prod/20231201/uuid.docx",
    "ossPdfPath": "prod/20231201/uuid.pdf"
  }
}
```

> ⚠️ **Known issue:** Direct `GET` of `https://flk.npc.gov.cn/{ossWordPath}` returns the SPA index page. These paths are for reference only; use the **Download API** above for actual downloads.

### Download via Browser

If the API path fails for a specific law:

1. Visit detail page: `browser_visit` with `https://flk.npc.gov.cn/detail?id={bbbs}`
2. Click 下载 button
3. Click 点击下载 element to trigger browser download
4. Check browser downloads folder for the file

## Browser Console Method (for API Discovery & Debugging)

This method lets you discover APIs by watching network traffic in Chrome DevTools.

### Step-by-Step

**1. Open DevTools**
- Press F12 in Chrome
- Click the **Network** tab
- Clear existing requests (click the 🚫 clear button)

**2. Perform the Action**
- Do something on the website (e.g., click 下载, or search)
- Watch the Network tab for new requests

**3. Find the API Call**
- Look for XHR/Fetch requests (filtered by the "Fetch/XHR" button)
- Click on a request to see:
  - **Headers**: URL, method, request headers
  - **Payload**: Request body data
  - **Response**: Server response

**4. Copy as Fetch**
- Right-click on the request → Copy → Copy as fetch
- Paste into Console to test:

```javascript
// Example: copied fetch for detail API
fetch("https://flk.npc.gov.cn/law-search/search/flfgDetails?bbbs=YOUR_ID", {
  method: "GET",
  headers: {
    "Accept": "application/json",
    "Referer": "https://flk.npc.gov.cn/"
  }
})
.then(r => r.json())
.then(data => console.log(data))
```

**5. Extract Specific Data**

```javascript
// Extract file URLs from detail response
fetch("https://flk.npc.gov.cn/law-search/search/flfgDetails?bbbs=YOUR_ID", {
  headers: { "Accept": "application/json", "Referer": "https://flk.npc.gov.cn/" }
})
.then(r => r.json())
.then(d => {
  const oss = d.data.ossFile;
  console.log("WORD:", "https://flk.npc.gov.cn/" + oss.ossWordPath);
  console.log("PDF:", "https://flk.npc.gov.cn/" + oss.ossPdfPath);
});
```

**6. Extract IDs from Search Results**

```javascript
// Run on /search page to get all visible law IDs
const items = Array.from(document.querySelectorAll('a[href*="detail"]'))
  .map(a => {
    const m = a.href.match(/[?&]id=([^&]+)/);
    return m ? { title: a.textContent.trim(), bbbs: decodeURIComponent(m[1]) } : null;
  })
  .filter(Boolean);
console.log(JSON.stringify(items, null, 2));
copy(items);  // Copies to clipboard
```

### Useful Console Snippets

```javascript
// Get current page's law metadata from the Vue/React state
// (The site is a Vue SPA, data may be in __VUE__ or window objects)
Object.keys(window).filter(k => k.includes('vue') || k.includes('VUE'))

// Check if there's a global app instance
window.__VUE__ || window.__VUE_APP__ || window.app

// Extract all visible law titles
Array.from(document.querySelectorAll('.result-title, .law-title, [class*="title"]'))
  .map(el => el.textContent.trim())
  .filter(t => t.length > 0);

// Monitor all fetch requests
const origFetch = window.fetch;
window.fetch = function(...args) {
  console.log('FETCH:', args[0], args[1]);
  return origFetch.apply(this, args);
};

// Get the current Vue/Pinia store state (if accessible)
const app = document.querySelector('#app').__vue_app__;
if (app) console.log(app.config.globalProperties);
```

### Capturing API Payloads from the Browser

When the documented payload stops working (e.g., after a site update):

1. Go to `/search`, open Network tab
2. Type a keyword and click search
3. Look for the POST request to `/law-search/search/list`
4. Copy it as fetch and compare the payload structure with the working example above
5. Update `scripts/download.py` and this doc with the new field names

## Response Fields Reference

### Law Item (from detail API)

| Field | Type | Description |
|-------|------|-------------|
| bbbs | string | Unique ID |
| title | string | Law title |
| flxz | string | Category (法律法规分类) |
| zdjgName | string | Issuing authority name |
| gbrq | string | Publish date (YYYY-MM-DD) |
| sxrq | string | Effective date (YYYY-MM-DD) |
| sxx | int | Status code: 3=有效, others=check enumData |
| ossFile | object | Contains file path fields |
| content | object | Document structure with chapters/articles |
| xgwj | array | Related documents |

### ossFile Object

| Field | Description |
|-------|-------------|
| ossWordPath | DOCX file path (WPS version) |
| ossPdfPath | PDF file path (gazette version) |
| ossWordOfdPath | OFD format (WPS version) |
| ossPdfOfdPath | OFD format (gazette version) |

All paths are relative to `https://flk.npc.gov.cn/`.
